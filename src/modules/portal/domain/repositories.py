from typing import List, Protocol

from src.modules.portal.domain.models import (
    CosechaDelProductor,
    FincaDelProductor,
    LoteDelProductor,
    MovimientoDelProductor,
)


class PortalRepository(Protocol):
    def fincas(self, usuario_id: int) -> List[FincaDelProductor]: ...
    def cosechas(self, usuario_id: int) -> List[CosechaDelProductor]: ...
    def movimientos(self, usuario_id: int) -> List[MovimientoDelProductor]: ...
    def lotes(self, usuario_id: int) -> List[LoteDelProductor]: ...
