"""Handler de AWS Lambda para la etapa 2 (PDF -> Markdown).

Evento (todas las claves son opcionales):
    {"bucket": "curso-miax-pipeline-fondos", "prefijo": "bestinver", "fecha": "AAAAMMDD",
     "ficheros": ["bestinfond_datos_fundamentales.pdf"], "ocr": "auto", "idioma": "spa",
     "sobrescribir": false}

Devuelve el resumen de `convertir_pdfs` (convertidos, omitidos y fallos).
"""

from common import almacenamiento_s3 as alm
from pdf_a_markdown import convertir_pdfs


def handler(event, context):
    event = event or {}
    return convertir_pdfs(
        bucket=event.get("bucket", alm.BUCKET_POR_DEFECTO),
        prefijo=event.get("prefijo", alm.PREFIJO_POR_DEFECTO),
        fecha=event.get("fecha"),
        ficheros=event.get("ficheros"),
        modo_ocr=event.get("ocr", "auto"),
        idioma=event.get("idioma", "spa"),
        sobrescribir=bool(event.get("sobrescribir", False)),
    )
