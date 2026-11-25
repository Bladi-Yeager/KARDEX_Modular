from src.modules.auth.domain.models import rol_efectivo
from src.modules.portal.application.dtos import (
    ClienteAdminOut,
    CosechaPortalOut,
    FincaPortalOut,
    LotePortalOut,
    MovimientoPortalOut,
    ResumenPortalOut,
)
from src.modules.portal.domain.repositories import PortalRepository
from src.modules.kardex.domain.saldos import resumen_por_producto


class PortalService:
    """Casos de uso del portal. Todo es de solo lectura."""

    def __init__(self, repository: PortalRepository):
        self.repository = repository

    def resumen(self, usuario) -> ResumenPortalOut:
        fincas = self.repository.fincas(usuario.id)
        cosechas = self.repository.cosechas(usuario.id)
        movimientos = self.repository.movimientos(usuario.id)

        fechas = [c.fecha for c in cosechas] + [m.fecha for m in movimientos]
        ultima = max(fechas) if fechas else None

        total_kg = round(sum(c.kg for c in cosechas), 3)
        entradas = round(sum(m.entrada_kg for m in movimientos), 3)
        salidas = round(sum(m.salida_kg for m in movimientos), 3)
        existencias = resumen_por_producto(cosechas, movimientos)
        unico = existencias[0] if len(existencias) == 1 and existencias[0]["unidad"] == "kg" else None

        return ResumenPortalOut(
            productor=usuario.nombre_completo,
            username=usuario.username,
            fincas=len(fincas),
            hectareas=round(sum(f.hectareas for f in fincas), 2),
            total_cosechas=len(cosechas),
            total_kg=total_kg,
            total_monto_bs=round(sum(c.monto_bs for c in cosechas), 2),
            entradas_kg=entradas,
            salidas_kg=salidas,
            saldo_kg=unico["saldo"] if unico else 0,
            ultima_actividad=ultima,
            tiene_datos=bool(fincas or cosechas or movimientos),
            existencias=existencias,
        )

    def fincas(self, usuario) -> list[FincaPortalOut]:
        return [FincaPortalOut(**vars(f)) for f in self.repository.fincas(usuario.id)]

    def cosechas(self, usuario) -> list[CosechaPortalOut]:
        return [CosechaPortalOut(**vars(c)) for c in self.repository.cosechas(usuario.id)]

    def movimientos(self, usuario) -> list[MovimientoPortalOut]:
        return [
            MovimientoPortalOut(**vars(m)) for m in self.repository.movimientos(usuario.id)
        ]

    def lotes(self, usuario) -> list[LotePortalOut]:
        return [LotePortalOut(**vars(l)) for l in self.repository.lotes(usuario.id)]

    # ------------------------------------------------------------------ admin
    def clientes(self, usuarios_repo) -> list[ClienteAdminOut]:
        """Lista los usuarios con rol cliente y las fincas que tienen asignadas."""
        salida = []
        for usuario in usuarios_repo.list_all():
            if rol_efectivo(usuario.rol) != "cliente":
                continue
            fincas = self.repository.fincas(usuario.id)
            salida.append(
                ClienteAdminOut(
                    id=usuario.id,
                    username=usuario.username,
                    nombre_completo=usuario.nombre_completo,
                    activo=usuario.activo,
                    fincas=[FincaPortalOut(**vars(f)) for f in fincas],
                )
            )
        return salida
