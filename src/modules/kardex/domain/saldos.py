from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from src.modules.kardex.domain.exceptions import OperacionKardexError

HISTORICO = "Histórico sin clasificar"


def validar_cantidad(cantidad, unidad):
    if unidad != "kg" and int(cantidad) != cantidad:
        raise OperacionKardexError("Las piezas y cajas se registran en cantidades enteras.")


def datos_producto(producto):
    return {
        "producto_id": producto.id if producto else None,
        "producto": producto.nombre if producto else HISTORICO,
        "unidad": producto.unidad if producto else "kg",
    }


def cantidades(movimiento):
    entrada = movimiento.cantidad_entrada if movimiento.cantidad_entrada is not None else movimiento.entrada_kg
    salida = movimiento.cantidad_salida if movimiento.cantidad_salida is not None else movimiento.salida_kg
    return Decimal(str(entrada)), Decimal(str(salida))


def acumular_por_producto(movimientos):
    """Recorre filas ordenadas sin compartir el acumulador entre productos."""
    saldos = defaultdict(Decimal)
    for movimiento, producto_id in movimientos:
        entrada, salida = cantidades(movimiento)
        saldos[producto_id] += entrada - salida
        yield saldos[producto_id]


def resumen_por_producto(cosechas, movimientos, desde=None, hasta=None):
    """Devuelve existencias, recepciones y actividad del período de cada producto."""
    grupos = {}
    por_id = {mov.id: mov for mov in movimientos}

    def grupo(registro):
        identidad = registro.producto_id
        if identidad not in grupos:
            grupos[identidad] = {
                "producto_id": identidad, "producto": registro.producto, "unidad": registro.unidad,
                "entrada": Decimal(0), "salida": Decimal(0), "saldo": Decimal(0), "apertura": Decimal(0),
                "recibida": Decimal(0), "rechazada": Decimal(0), "merma": Decimal(0),
                "semanas": defaultdict(lambda: [Decimal(0), Decimal(0)]),
            }
        return grupos[identidad]

    for cosecha in cosechas:
        fecha = cosecha.fecha_recepcion or cosecha.fecha
        if (desde and fecha < desde) or (hasta and fecha > hasta):
            continue
        fila = grupo(cosecha)
        fila["recibida"] += Decimal(str(cosecha.recibida if cosecha.recibida is not None else cosecha.cantidad))
        fila["rechazada"] += Decimal(str(cosecha.rechazada or 0))

    for mov in movimientos:
        if hasta and mov.fecha > hasta:
            continue
        fila = grupo(mov)
        fila["saldo"] = Decimal(str(mov.cantidad_saldo))
        if desde and mov.fecha < desde:
            fila["apertura"] = fila["saldo"]
            continue
        entrada, salida = cantidades(mov)
        fila["entrada"] += entrada
        fila["salida"] += salida
        original = por_id.get(getattr(mov, "anula_movimiento_id", None))
        if mov.tipo == "merma":
            fila["merma"] += salida
        if original and original.tipo == "merma":
            fila["merma"] -= entrada
        semana = mov.fecha - timedelta(days=mov.fecha.weekday())
        acumulado = fila["semanas"][semana]
        acumulado[0] += entrada
        acumulado[1] += salida

    for fila in grupos.values():
        fila["semanas"] = [{"fecha": fecha, "entrada": cantidades_semana[0], "salida": cantidades_semana[1]}
                            for fecha, cantidades_semana in sorted(fila["semanas"].items())]
    return sorted(grupos.values(), key=lambda fila: (fila["producto_id"] is None, fila["producto"].casefold(), fila["unidad"]))
