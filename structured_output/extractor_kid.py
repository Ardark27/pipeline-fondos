"""Extracción de datos estructurados de un KID a partir de su versión en Markdown.

Lee el Markdown de  s3://<bucket>/markdown/<prefijo>/<AAAAMMDD>/<slug>_datos_fundamentales.md
(generado con `pdf_markdown/pdf_a_markdown.py`) y guarda el JSON en
                    s3://<bucket>/extraction/<prefijo>/<AAAAMMDD>/<slug>_datos_fundamentales.json

Uso:
    python extractor_kid.py                               # KID de Bestinfond, última fecha
    python extractor_kid.py bestinver-renta bestvalue     # KID de esos fondos (slugs)
    python extractor_kid.py --todos                       # todos los KID de la carpeta
    python extractor_kid.py --fecha 20261119              # una fecha concreta
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Optional

from pydantic import BaseModel, Field
from langchain_aws import ChatBedrockConverse

# Raíz del repo en el path para poder importar el paquete común al ejecutar el script directamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import almacenamiento_s3 as alm  # noqa: E402

MODELO = "global.moonshotai.kimi-k3.1"
REGION_BEDROCK = "eu-west-3"
TIPO_KID = "datos_fundamentales"


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


def extraer(model_with_structure, texto: str) -> DatosKID:
    return model_with_structure.invoke(
        "Extrae los datos de este documento KID (en formato Markdown). Para cada campo, rellena también su campo "
        "'_evidencia' con el fragmento copiado literalmente del texto (sin la marca Markdown) de donde sale el dato.\n\n"
        f"{texto}"
    )


def extraer_kids(
    bucket: str = alm.BUCKET_POR_DEFECTO,
    prefijo: str = alm.PREFIJO_POR_DEFECTO,
    fecha: str | None = None,
    fondos: list[str] | None = None,
    todos: bool = False,
) -> dict:
    """Extrae los datos de los KID en Markdown de markdown/<prefijo>/<fecha>/ y sube los JSON a extraction/.

    `fecha` por defecto es la más reciente en markdown/. Se procesan los KID de los `fondos`
    indicados (slugs; por defecto bestinfond) o, con `todos`, todos los de la carpeta.
    Devuelve un resumen con los JSON subidos y los fallos.
    """
    s3 = alm.conectar(bucket)
    fecha = alm.resolver_fecha(s3, bucket, alm.CARPETA_MARKDOWN, prefijo, fecha)
    origen = alm.carpeta(alm.CARPETA_MARKDOWN, prefijo, fecha)
    destino = alm.carpeta(alm.CARPETA_EXTRACCION, prefijo, fecha)
    print(f"Origen:  s3://{bucket}/{origen}/")
    print(f"Destino: s3://{bucket}/{destino}/\n")

    if todos:
        claves = [c for c in alm.listar_claves(s3, bucket, origen, ".md")
                  if PurePosixPath(c).stem.endswith(f"_{TIPO_KID}")]
    else:
        claves = [f"{origen}/{slug}_{TIPO_KID}.md" for slug in (fondos or ["bestinfond"])]
    if not claves:
        raise alm.ErrorEtapa(
            f"no se ha encontrado ningún KID en Markdown en s3://{bucket}/{origen}/. "
            "Genéralo antes con: python pdf_markdown/pdf_a_markdown.py"
        )

    model = ChatBedrockConverse(model=MODELO, region_name=REGION_BEDROCK)
    model_with_structure = model.with_structured_output(DatosKID, method="json_schema")

    extraidos, fallos = [], []
    for i, clave_md in enumerate(claves, 1):
        nombre = PurePosixPath(clave_md).name
        clave_json = f"{destino}/{PurePosixPath(clave_md).stem}.json"
        print(f"[{i}/{len(claves)}] {nombre} -> s3://{bucket}/{clave_json}")
        try:
            if not alm.existe(s3, bucket, clave_md):
                raise FileNotFoundError(f"no existe s3://{bucket}/{clave_md}")
            texto = alm.leer(s3, bucket, clave_md).decode("utf-8")
            datos = extraer(model_with_structure, texto)
            verificacion = verificar_evidencias(datos, texto)
            resultado = {
                "markdown_origen": clave_md,
                "modelo": MODELO,
                "datos": datos.model_dump(mode="json"),
                "verificacion_evidencias": verificacion,
            }
            alm.escribir(
                s3, bucket, clave_json,
                json.dumps(resultado, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json; charset=utf-8",
                {"markdown-origen": clave_md},
            )
            print(f"    {datos.nombre_producto} ({datos.isin}), SRI {datos.sri}")
            for campo, encontrada in verificacion.items():
                print(f"      {'OK   ' if encontrada else 'FALLO'} evidencia de {campo}")
            extraidos.append(clave_json)
        except Exception as error:  # un KID que falle no debe parar el resto
            print(f"    ERROR: {error}")
            fallos.append({"fichero": nombre, "error": str(error)})

    print("\nResumen:")
    print(f"  Extraídos y subidos: {len(extraidos)}")
    print(f"  Fallos: {len(fallos)}")
    for fallo in fallos:
        print(f"    - {fallo['fichero']}: {fallo['error']}")
    return {
        "bucket": bucket, "origen": origen, "destino": destino, "fecha": fecha,
        "extraidos": extraidos, "fallos": fallos,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fondos", nargs="*", default=["bestinfond"], help="Slugs de los fondos (por defecto bestinfond)")
    parser.add_argument("--todos", action="store_true", help="Procesa todos los KID de la carpeta")
    parser.add_argument("--bucket", default=alm.BUCKET_POR_DEFECTO, help="Bucket de S3")
    parser.add_argument("--prefijo", default=alm.PREFIJO_POR_DEFECTO, help="Gestora (carpeta dentro de cada etapa)")
    parser.add_argument(
        "--fecha", type=alm.fecha_valida,
        help="Carpeta de fecha AAAAMMDD (por defecto, la más reciente en markdown/)",
    )
    args = parser.parse_args()

    try:
        resumen = extraer_kids(args.bucket, args.prefijo, args.fecha, args.fondos, args.todos)
    except alm.ErrorEtapa as e:
        print(f"[error] {e}")
        return 1
    return 1 if resumen["fallos"] else 0


if __name__ == "__main__":
    sys.exit(main())
