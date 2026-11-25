from decimal import Decimal

from sqlalchemy import and_, case, extract, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.fechas import hoy_bolivia
from src.modules.inventory.infrastructure.models_db import FincaDB, LoteDB, ParcelaDB, ProductoDB
from src.modules.kardex.domain.exceptions import OperacionKardexError
from src.modules.kardex.domain.models import Cosecha, Movimiento
from src.modules.kardex.domain.saldos import acumular_por_producto, cantidades, datos_producto, validar_cantidad
from src.modules.kardex.infrastructure.models_db import ControlKardexDB, CosechaDB, MovimientoDB
from src.modules.supliers.infrastructure.models_db import CosecheroDB


def finca_del_movimiento():
    # Una referencia histórica contradictoria queda sin finca asignable.
    return case(
        (and_(MovimientoDB.finca_id.is_not(None), LoteDB.finca_id.is_not(None),
              MovimientoDB.finca_id != LoteDB.finca_id), None),
        else_=func.coalesce(MovimientoDB.finca_id, LoteDB.finca_id),
    )


def datos_recepcion(row, lote):
    def numero(valor):
        return float(valor) if valor is not None else None

    return {
        "cantidad": float(row.cantidad if row.cantidad is not None else row.kg),
        "recibida": numero(row.recibida), "rechazada": numero(row.rechazada),
        "motivo_rechazo": row.motivo_rechazo,
        "cantidad_secundaria": numero(row.cantidad_secundaria),
        "unidad_secundaria": row.unidad_secundaria,
        "fecha_recepcion": lote.fecha_ingreso if lote else None,
        "documento_recepcion": row.documento_recepcion,
    }


def datos_movimiento(row, producto, saldo):
    entrada, salida = cantidades(row)
    return {
        **datos_producto(producto),
        "cantidad_entrada": float(entrada), "cantidad_salida": float(salida), "cantidad_saldo": float(saldo),
        "entrada_kg": float(row.entrada_kg), "salida_kg": float(row.salida_kg),
        "saldo_kg": float(saldo) if producto is None or producto.unidad == "kg" else 0.0,
        "tipo": row.tipo or "movimiento",
    }


class CosechaRepositoryImpl:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_domain(row, lote, producto) -> Cosecha:
        return Cosecha(
            id=row.id, fecha=row.fecha, cosechero_id=row.cosechero_id, finca_id=row.finca_id,
            parcela_id=row.parcela_id, tipo_cosecha=row.tipo_cosecha, kg=float(row.kg),
            monto_bs=float(row.monto_bs), observacion=row.observacion, lote_id=lote.id if lote else None,
            borrador=row.borrador, **datos_producto(producto), **datos_recepcion(row, lote),
        )

    def _consulta(self):
        return (self.db.query(CosechaDB, LoteDB, ProductoDB)
                .outerjoin(LoteDB, LoteDB.cosecha_id == CosechaDB.id)
                .outerjoin(ProductoDB, CosechaDB.producto_id == ProductoDB.id))

    def list_all(self) -> list[Cosecha]:
        return [self._to_domain(*fila) for fila in self._consulta().order_by(CosechaDB.fecha, CosechaDB.id).all()]

    def get_by_id(self, cosecha_id: int) -> Cosecha | None:
        fila = self._consulta().filter(CosechaDB.id == cosecha_id).one_or_none()
        return self._to_domain(*fila) if fila else None

    def _validar(self, data):
        finca = self.db.get(FincaDB, data.finca_id)
        cosechero = self.db.get(CosecheroDB, data.cosechero_id)
        if finca is None or not finca.activo or cosechero is None or not cosechero.activo:
            raise OperacionKardexError("Selecciona un chaco y un cosechero activos.")
        if data.parcela_id is not None:
            parcela = self.db.get(ParcelaDB, data.parcela_id)
            if parcela is None or not parcela.activo or parcela.finca_id != finca.id:
                raise OperacionKardexError("Selecciona una parcela activa del mismo chaco.")
        producto = self.db.get(ProductoDB, data.producto_id)
        if producto is None:
            raise OperacionKardexError("Selecciona un producto del catálogo.")
        validar_cantidad(data.cantidad, producto.unidad)
        return producto

    def _guardar(self, row, data):
        producto = self._validar(data)
        for campo, valor in data.model_dump().items():
            setattr(row, campo, valor)
        row.tipo_cosecha = producto.nombre[:50]
        row.kg = data.cantidad if producto.unidad == "kg" else 0
        self.db.add(row)
        self.db.commit()
        return self._to_domain(row, None, producto)

    def add(self, data) -> Cosecha:
        return self._guardar(CosechaDB(borrador=True), data)

    def _borrador(self, cosecha_id):
        row = self.db.get(CosechaDB, cosecha_id, with_for_update=True)
        if row is None:
            raise OperacionKardexError("La cosecha indicada no existe.", 404)
        if not row.borrador:
            raise OperacionKardexError("Solo se puede modificar o eliminar una cosecha en borrador.", 409)
        return row

    def editar(self, cosecha_id, data):
        return self._guardar(self._borrador(cosecha_id), data)

    def eliminar(self, cosecha_id):
        self.db.delete(self._borrador(cosecha_id))
        self.db.commit()

    def total_kg_by_month(self, anio: int, mes: int) -> float:
        total = self.db.query(func.sum(CosechaDB.kg)).filter(
            extract("year", CosechaDB.fecha) == anio,
            extract("month", CosechaDB.fecha) == mes,
            CosechaDB.borrador.is_(False),
        ).scalar()
        return float(total or 0)


class MovimientoRepositoryImpl:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_domain(row, finca_id, cosecha_id, producto, saldo) -> Movimiento:
        return Movimiento(
            id=row.id, fecha=row.fecha, detalle=row.detalle, doc=row.doc, lote_id=row.lote_id,
            finca_id=finca_id, observacion=row.observacion, cosecha_id=cosecha_id,
            anula_movimiento_id=row.anula_movimiento_id, **datos_movimiento(row, producto, saldo),
        )

    def _consulta(self):
        return (self.db.query(MovimientoDB, finca_del_movimiento(), LoteDB.cosecha_id, ProductoDB)
                .outerjoin(LoteDB, MovimientoDB.lote_id == LoteDB.id)
                .outerjoin(ProductoDB, LoteDB.producto_id == ProductoDB.id)
                .order_by(MovimientoDB.fecha, MovimientoDB.id))

    def list_all(self, finca_id=None, lote_id=None, producto_id=None) -> list[Movimiento]:
        consulta = self._consulta()
        if finca_id is not None:
            consulta = consulta.filter(finca_del_movimiento() == finca_id)
        if lote_id is not None:
            consulta = consulta.filter(MovimientoDB.lote_id == lote_id)
        if producto_id is not None:
            consulta = consulta.filter(ProductoDB.id == producto_id if producto_id > 0 else ProductoDB.id.is_(None))
        filas = consulta.all()
        saldos = acumular_por_producto((row, producto.id if producto else None) for row, _, _, producto in filas)
        return [self._to_domain(*fila, saldo) for fila, saldo in zip(filas, saldos)]

    def _bloquear(self):
        resultado = self.db.execute(
            update(ControlKardexDB).where(ControlKardexDB.id == 1).values(revision=ControlKardexDB.revision)
        )
        if resultado.rowcount != 1:
            raise OperacionKardexError("El control del Kardex todavía no está inicializado.", 503)

    @staticmethod
    def _movimiento(producto, entrada, salida, **campos):
        unidad = producto.unidad if producto else "kg"
        validar_cantidad(entrada, unidad)
        validar_cantidad(salida, unidad)
        return MovimientoDB(
            **campos, cantidad_entrada=entrada, cantidad_salida=salida,
            entrada_kg=entrada if unidad == "kg" else 0, salida_kg=salida if unidad == "kg" else 0,
        )

    def _guardar(self, row, producto):
        self.db.add(row)
        self.db.flush()
        id_producto = producto.id if producto else None
        filas = self._consulta().filter(ProductoDB.id == id_producto).with_for_update().all()
        if cantidades(row)[1]:
            grupos = [
                ("almacén", [mov for mov, _, _, _ in filas]),
                ("chaco", [mov for mov, finca, _, _ in filas if finca == row.finca_id]),
            ]
            if row.lote_id is not None:
                grupos.append(("lote", [mov for mov, _, _, _ in filas if mov.lote_id == row.lote_id]))
            for nombre, grupo in grupos:
                saldos = acumular_por_producto((mov, id_producto) for mov in grupo)
                for mov, saldo in zip(grupo, saldos):
                    if (mov.fecha, mov.id) >= (row.fecha, row.id) and saldo < 0:
                        raise OperacionKardexError(f"La salida deja un saldo negativo de este producto en el {nombre}.", 409)
        resultado = None
        saldos = acumular_por_producto((mov, id_producto) for mov, _, _, _ in filas)
        for fila, saldo in zip(filas, saldos):
            mov = fila[0]
            if producto is None or producto.unidad == "kg":
                mov.saldo_kg = saldo
            if mov.id == row.id:
                resultado = self._to_domain(*fila, saldo)
        self.db.commit()
        return resultado

    def add(self, data, usuario_id: int) -> Movimiento:
        self._bloquear()
        if not data.lote_id:
            raise OperacionKardexError("Selecciona el lote para mantener identificado el producto.")
        lote = self.db.get(LoteDB, data.lote_id, with_for_update=True)
        if lote is None:
            raise OperacionKardexError("El lote indicado no existe.", 404)
        if data.finca_id and lote.finca_id and data.finca_id != lote.finca_id:
            raise OperacionKardexError("El lote pertenece a otro chaco.")
        if data.fecha < lote.fecha_ingreso:
            raise OperacionKardexError("La fecha debe ser igual o posterior al ingreso del lote.")
        if lote.cosecha_id and data.cantidad_entrada:
            raise OperacionKardexError("La entrada del lote vinculado se registra al recibir la cosecha.")
        finca = self.db.get(FincaDB, lote.finca_id or data.finca_id) if (lote.finca_id or data.finca_id) else None
        if finca is None or not finca.activo:
            raise OperacionKardexError("Selecciona un chaco activo para el movimiento.")
        producto = self.db.get(ProductoDB, lote.producto_id) if lote.producto_id else None
        if producto and data.unidad_legada and producto.unidad != data.unidad_legada:
            raise OperacionKardexError("Indica la cantidad en la unidad de inventario del producto.")
        row = self._movimiento(
            producto, data.cantidad_entrada, data.cantidad_salida,
            fecha=data.fecha, detalle=data.detalle, doc=data.doc, lote_id=lote.id, finca_id=finca.id,
            observacion=data.observacion, registrado_por=usuario_id, tipo=data.tipo,
        )
        return self._guardar(row, producto)

    def recibir(self, cosecha_id, data, usuario_id):
        self._bloquear()
        cosecha = self.db.get(CosechaDB, cosecha_id, with_for_update=True)
        if cosecha is None:
            raise OperacionKardexError("La cosecha indicada no existe.", 404)
        if not cosecha.borrador:
            raise OperacionKardexError("Esta cosecha ya fue recibida o es un registro histórico.", 409)
        producto = self.db.get(ProductoDB, cosecha.producto_id) if cosecha.producto_id else None
        if producto is None:
            raise OperacionKardexError("Edita el borrador y elige un producto antes de recibirlo.")
        llegada = data.recibida if data.recibida is not None else cosecha.cantidad
        if data.fecha < cosecha.fecha or llegada <= 0 or data.rechazada > llegada:
            raise OperacionKardexError("Verifica la fecha y que el rechazo no supere la cantidad recibida.")
        validar_cantidad(llegada, producto.unidad)
        validar_cantidad(data.rechazada, producto.unidad)
        if data.unidad_secundaria:
            if data.unidad_secundaria == producto.unidad:
                raise OperacionKardexError("La medición adicional debe usar otra unidad.")
            validar_cantidad(data.cantidad_secundaria, data.unidad_secundaria)
        aceptada = llegada - data.rechazada
        lote = LoteDB(codigo=data.codigo, finca_id=cosecha.finca_id, cosecha_id=cosecha.id,
                      fecha_ingreso=data.fecha, detalle=cosecha.tipo_cosecha, producto_id=producto.id)
        self.db.add(lote)
        try:
            self.db.flush()
        except IntegrityError as error:
            raise OperacionKardexError("El código de lote ya existe o la cosecha ya fue recibida.", 409) from error
        cosecha.borrador = False
        cosecha.cantidad = aceptada
        cosecha.kg = aceptada if producto.unidad == "kg" else 0
        if not aceptada:
            cosecha.monto_bs = 0
        elif data.monto_bs is not None:
            cosecha.monto_bs = data.monto_bs
        cosecha.recibida, cosecha.rechazada = llegada, data.rechazada
        cosecha.motivo_rechazo = data.motivo_rechazo.strip() if data.rechazada else None
        cosecha.cantidad_secundaria, cosecha.unidad_secundaria = data.cantidad_secundaria, data.unidad_secundaria
        cosecha.documento_recepcion = data.doc
        resultado = {"lote_id": lote.id, "codigo": lote.codigo, "unidad": producto.unidad,
                     "recibida": llegada, "rechazada": data.rechazada, "aceptada": aceptada, "movimiento": None}
        if not aceptada:
            self.db.commit()
            return resultado
        row = self._movimiento(
            producto, aceptada, Decimal(0), fecha=data.fecha, detalle=f"Recepción de cosecha #{cosecha.id}",
            doc=data.doc, lote_id=lote.id, finca_id=cosecha.finca_id, registrado_por=usuario_id, tipo="recepcion",
        )
        resultado["movimiento"] = self._guardar(row, producto)
        return resultado

    def anular(self, movimiento_id: int, motivo: str, usuario_id: int) -> Movimiento:
        self._bloquear()
        fila = self._consulta().filter(MovimientoDB.id == movimiento_id).with_for_update().one_or_none()
        if fila is None:
            raise OperacionKardexError("El movimiento indicado no existe.", 404)
        original, finca, _, producto = fila
        ya_anulado = self.db.query(MovimientoDB.id).filter_by(anula_movimiento_id=movimiento_id).with_for_update().first()
        if original.anula_movimiento_id is not None or ya_anulado:
            raise OperacionKardexError("El movimiento ya está anulado o es una anulación.", 409)
        entrada, salida = cantidades(original)
        if finca is None or bool(entrada) == bool(salida):
            raise OperacionKardexError("Revisa el ámbito y las cantidades del movimiento histórico antes de anularlo.", 409)
        row = self._movimiento(
            producto, salida, entrada, fecha=max(hoy_bolivia(), original.fecha),
            detalle=f"Anulación del movimiento #{original.id}", doc=original.doc, lote_id=original.lote_id,
            finca_id=finca, observacion=motivo, anula_movimiento_id=original.id, registrado_por=usuario_id, tipo="anulacion",
        )
        return self._guardar(row, producto)
