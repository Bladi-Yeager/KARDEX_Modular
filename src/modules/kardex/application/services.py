from src.modules.kardex.domain.models import Cosecha, Movimiento
from src.modules.kardex.domain.repositories import CosechaRepository, MovimientoRepository
from src.modules.kardex.domain.exceptions import CosechaNoEncontrada
from src.modules.kardex.application.dtos import CosechaCreate, MovimientoCreate, RecepcionCreate


class CosechaService:
    def __init__(self, repository: CosechaRepository):
        self.repository = repository

    def list_all(self):
        return self.repository.list_all()

    def get_by_id(self, cosecha_id: int) -> Cosecha:
        cosecha = self.repository.get_by_id(cosecha_id)
        if not cosecha:
            raise CosechaNoEncontrada(cosecha_id)
        return cosecha

    def create(self, data: CosechaCreate) -> Cosecha:
        return self.repository.add(data)

    def total_kg_by_month(self, anio: int, mes: int) -> float:
        return self.repository.total_kg_by_month(anio, mes)

    def editar(self, cosecha_id: int, data: CosechaCreate) -> Cosecha:
        return self.repository.editar(cosecha_id, data)

    def eliminar(self, cosecha_id: int) -> None:
        self.repository.eliminar(cosecha_id)


class MovimientoService:
    def __init__(self, repository: MovimientoRepository):
        self.repository = repository

    def list_all(self, finca_id: int | None = None, lote_id: int | None = None, producto_id: int | None = None):
        return self.repository.list_all(finca_id, lote_id, producto_id)

    def create(self, data: MovimientoCreate, usuario_id: int) -> Movimiento:
        return self.repository.add(data, usuario_id)

    def recibir(self, cosecha_id: int, data: RecepcionCreate, usuario_id: int):
        return self.repository.recibir(cosecha_id, data, usuario_id)

    def anular(self, movimiento_id: int, motivo: str, usuario_id: int) -> Movimiento:
        return self.repository.anular(movimiento_id, motivo, usuario_id)
