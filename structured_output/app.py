"""Handler de AWS Lambda para la etapa 3 (extracción de datos del KID con un LLM).

Evento (todas las claves son opcionales):
    {"bucket": "curso-miax-pipeline-fondos", "prefijo": "bestinver", "fecha": "AAAAMMDD",
     "todos": true}
    o, en lugar de "todos", "fondos": ["bestinver-renta", "bestvalue"] (por defecto, bestinfond)
    o "claves": ["markdown/<prefijo>/<fecha>/<slug>_<tipo>.md", ...] (solo se usan los KID).

La salida de la etapa 2 es un evento válido: se procesan los KID de su "claves".

Devuelve el resumen de `extraer_kids`:
    {"bucket": ..., "prefijo": ..., "fecha": ..., "origen": ..., "destino": ...,
     "claves": ["extraction/<prefijo>/<fecha>/<slug>_datos_fundamentales.json", ...], "fallos": [...]}
"""

from common import almacenamiento_s3 as alm
from extractor_kid import extraer_kids


def handler(event, context):
    event = alm.evento_lambda(event)
    return extraer_kids(
        bucket=event.get("bucket", alm.BUCKET_POR_DEFECTO),
        prefijo=event.get("prefijo", alm.PREFIJO_POR_DEFECTO),
        fecha=event.get("fecha"),
        fondos=event.get("fondos"),
        todos=bool(event.get("todos", False)),
        claves=event.get("claves"),
    )
