"""Handler de AWS Lambda para la etapa 1 (descarga de documentos de Bestinver).

Evento (todas las claves son opcionales):
    {"bucket": "curso-miax-pipeline-fondos", "prefijo": "bestinver", "fecha": "AAAAMMDD", "delay": 1.0}

Devuelve el resumen de `descargar_documentos` (claves subidas y fallos).
"""

from common import almacenamiento_s3 as alm
from descargar_kids_bestinver import descargar_documentos


def handler(event, context):
    event = event or {}
    return descargar_documentos(
        bucket=event.get("bucket", alm.BUCKET_POR_DEFECTO),
        prefijo=event.get("prefijo", alm.PREFIJO_POR_DEFECTO),
        fecha=event.get("fecha"),
        delay=float(event.get("delay", 1.0)),
    )
