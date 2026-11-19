"""Extracción de datos estructurados de un KID a partir de su versión en Markdown.

El PDF se convierte antes a Markdown con `pdf_a_markdown.py`.

Uso:
    python ejemplo_kid.py                                   # KID de Bestinfond
    python ejemplo_kid.py ruta/al/kid_datos_fundamentales.md
"""

import argparse
import re
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from langchain_aws import ChatBedrockConverse


DESCRIPCION_EVIDENCIA = (
    "Fragmento LITERAL del documento del que se ha extraído el campo anterior, "
    "copiado exactamente como aparece en el texto (mismas palabras, números y signos, "
    "sin traducir, resumir ni corregir). Breve: la frase o línea mínima que contiene el dato. "
    "Vacío (null) si el campo no aparece en el documento."
)


def evidencia(campo: str) -> Optional[str]:
    """Campo de evidencia asociado a otro campo extraído."""
    return Field(None, description=f"Evidencia de '{campo}'. {DESCRIPCION_EVIDENCIA}")


class DatosKID(BaseModel):
    """Datos fundamentales de un fondo de inversión, cada uno con su evidencia literal."""

    isin: str = Field(
        ...,
        description="Código ISIN de la clase (12 caracteres)",
        pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$",
    )
    isin_evidencia: Optional[str] = evidencia("isin")

    nombre_producto: str = Field(..., description="Nombre del fondo tal y como aparece en el KID")
    nombre_producto_evidencia: Optional[str] = evidencia("nombre_producto")

    nombre_clase: Optional[str] = Field(
        None, description="Clase o serie del fondo (p. ej. «Clase C», «P Acc EUR»)"
    )
    nombre_clase_evidencia: Optional[str] = evidencia("nombre_clase")

    gestora: str = Field(..., description="Productor del PRIIP / sociedad gestora")
    gestora_evidencia: Optional[str] = evidencia("gestora")

    fecha_documento: Optional[date] = Field(
        None, description="Fecha de validez del KID (formato AAAA-MM-DD)"
    )
    fecha_documento_evidencia: Optional[str] = evidencia("fecha_documento")

    sri: int = Field(..., ge=1, le=7, description="Indicador resumido de riesgo (SRI), de 1 a 7")
    sri_evidencia: Optional[str] = evidencia("sri")

    periodo_mantenimiento_anios: Optional[float] = Field(
        None, description="Período de mantenimiento recomendado, en años"
    )
    periodo_mantenimiento_anios_evidencia: Optional[str] = evidencia("periodo_mantenimiento_anios")

    gastos_corrientes_pct: Optional[float] = Field(
        None,
        description=(
            "Comisiones de gestión y otros costes administrativos o de funcionamiento, "
            "en % anual (p. ej. 1.78 para un 1,78 %)"
        ),
    )
    gastos_corrientes_pct_evidencia: Optional[str] = evidencia("gastos_corrientes_pct")

    costes_entrada_pct: Optional[float] = Field(
        None, description="Costes de entrada, en % (p. ej. 0 si no se cobran)"
    )
    costes_entrada_pct_evidencia: Optional[str] = evidencia("costes_entrada_pct")

    costes_salida_pct: Optional[float] = Field(
        None, description="Costes de salida, en % (p. ej. 0 si no se cobran)"
    )
    costes_salida_pct_evidencia: Optional[str] = evidencia("costes_salida_pct")


def normalizar(texto: str) -> str:
    """Quita la marca Markdown y colapsa espacios para comparar fragmentos con el documento.

    Se eliminan todos los espacios porque el OCR y el formato Markdown parten a veces las
    palabras (p. ej. «adqui ~~r~~ i ~~r~~»).
    """
    texto = re.sub(r"[*_~`#|>]", "", texto)
    return re.sub(r"\s+", "", texto).lower()


def verificar_evidencias(datos: DatosKID, texto: str) -> dict[str, bool]:
    """Comprueba, para cada campo *_evidencia, si el fragmento aparece en el texto del documento."""
    texto_norm = normalizar(texto)
    resultado = {}
    for nombre, valor in datos.model_dump().items():
        if nombre.endswith("_evidencia") and valor:
            resultado[nombre.removesuffix("_evidencia")] = normalizar(valor) in texto_norm
    return resultado


RUTA_POR_DEFECTO = (
    Path(__file__).resolve().parent.parent
    / "descargas" / "bestinver" / "bestinfond_datos_fundamentales.md"
)

parser = argparse.ArgumentParser(description="Extrae los datos de un KID convertido a Markdown.")
parser.add_argument("markdown", nargs="?", type=Path, default=RUTA_POR_DEFECTO, help="Fichero .md del KID")
args = parser.parse_args()
if not args.markdown.exists():
    raise SystemExit(
        f"No existe '{args.markdown}'. Genera antes el Markdown con: python pdf_a_markdown.py"
    )
texto = args.markdown.read_text(encoding="utf-8")

model = ChatBedrockConverse(model="global.moonshotai.kimi-k3.1", region_name="eu-west-3")
model_with_structure = model.with_structured_output(DatosKID, method="json_schema")

response = model_with_structure.invoke(
    "Extrae los datos de este documento KID (en formato Markdown). Para cada campo, rellena también su campo "
    "'_evidencia' con el fragmento copiado literalmente del texto (sin la marca Markdown) de donde sale el dato.\n\n"
    f"{texto}"
)
print(response)

print("\nVerificación de evidencias:")
for campo, encontrada in verificar_evidencias(response, texto).items():
    print(f"  {'OK   ' if encontrada else 'FALLO'} {campo}")
