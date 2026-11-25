from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils import get_column_letter

TIPO_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def libro_excel(nombre, columnas, filas):
    libro = Workbook()
    hoja = libro.active
    hoja.title = nombre[:31]
    hoja.freeze_panes = "A2"
    hoja.append([titulo for _, titulo in columnas])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="203D52")
    for fila in filas:
        valores = (fila.get(campo) for campo, _ in columnas)
        hoja.append([ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v for v in valores])
        for celda in hoja[hoja.max_row]:
            valor = celda.value
            if isinstance(valor, str):
                # Los valores de negocio siempre son texto, incluso si empiezan con "=".
                celda.data_type = "s"
            elif isinstance(valor, (date, datetime)):
                celda.number_format = "dd/mm/yyyy" if type(valor) is date else "dd/mm/yyyy hh:mm"
            elif isinstance(valor, float):
                celda.number_format = "#,##0.000" if columnas[celda.column - 1][0].endswith(("_kg", "kg")) else "#,##0.00"
            if celda.row % 2 == 0:
                celda.fill = PatternFill("solid", fgColor="F1F6F7")
            celda.alignment = Alignment(vertical="center")
    hoja.auto_filter.ref = hoja.dimensions
    for indice, (_, titulo) in enumerate(columnas, 1):
        valores = (len(str(celda.value or "")) for celda in hoja[get_column_letter(indice)])
        hoja.column_dimensions[get_column_letter(indice)].width = min(52, max(len(titulo) + 3, max(valores, default=0) + 3, 12))
    archivo = BytesIO()
    libro.save(archivo)
    return archivo.getvalue()
