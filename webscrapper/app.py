"""Handler de AWS Lambda para la etapa 1 (descarga de documentos de Bestinver).

Pensado para lanzarse con un horario de AWS. Admite tres formas de evento:

1. EventBridge Scheduler (recomendado). En el "Input" del schedule se pone:
       {"time": "<aws.scheduler.scheduled-time>"}
   Scheduler sustituye <aws.scheduler.scheduled-time> por la hora programada
   (ISO 8601 en UTC, p. ej. "2026-11-26T06:00:00Z"). Se pueden añadir el resto de
   parámetros: {"time": "<aws.scheduler.scheduled-time>", "prefijo": "bestinver", "delay": 1.0}

2. Regla programada de EventBridge (rate/cron), que envía su evento estándar:
       {"source": "aws.events", "detail-type": "Scheduled Event",
        "time": "2026-11-26T06:00:00Z", "detail": {}, ...}
   Los parámetros, si se quieren, van en "detail".

3. Invocación directa (todas las claves son opcionales):
       {"bucket": "curso-miax-pipeline-fondos", "prefijo": "bestinver", "fecha": "AAAAMMDD", "delay": 1.0}

Si el evento no trae "fecha" pero sí "time", la carpeta de fecha es el día (UTC) de la hora
programada. Así, si el scheduler reintenta la invocación más tarde, se escribe en la misma
carpeta. Sin "fecha" ni "time", se usa el día de hoy.

Devuelve el resumen de `descargar_documentos`, que es el evento de entrada de la etapa 2:
    {"bucket": ..., "prefijo": ..., "fecha": ..., "carpeta": ...,
     "claves": ["download/<prefijo>/<fecha>/<slug>_<tipo>.pdf", ...], "fallos": [...]}
"""

from datetime import datetime, timezone

from common import almacenamiento_s3 as alm
from descargar_kids_bestinver import descargar_documentos


def fecha_de_hora(hora: str) -> str:
    """Convierte una hora ISO 8601 ("2026-11-26T06:00:00Z") en la fecha AAAAMMDD en UTC."""
    try:
        momento = datetime.fromisoformat(hora)
    except (TypeError, ValueError):
        raise ValueError(f"hora programada no válida '{hora}', se espera ISO 8601 (p. ej. 2026-11-26T06:00:00Z)")
    if momento.tzinfo is None:  # sin zona horaria: se asume UTC, como envía AWS
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc).strftime("%Y%m%d")


def parametros_evento(event) -> dict:
    """Parámetros de la etapa a partir de un evento de Scheduler, de una regla de EventBridge o directo."""
    event = alm.evento_lambda(event)
    parametros = dict(event)
    if isinstance(event.get("detail"), dict):  # regla programada de EventBridge
        parametros.update(event["detail"])
    if not parametros.get("fecha") and parametros.get("time"):
        parametros["fecha"] = fecha_de_hora(parametros["time"])
    return parametros


def handler(event, context):
    parametros = parametros_evento(event)
    print(f"Parámetros: fecha={parametros.get('fecha') or 'hoy'}, "
          f"prefijo={parametros.get('prefijo', alm.PREFIJO_POR_DEFECTO)}")
    return descargar_documentos(
        bucket=parametros.get("bucket", alm.BUCKET_POR_DEFECTO),
        prefijo=parametros.get("prefijo", alm.PREFIJO_POR_DEFECTO),
        fecha=parametros.get("fecha"),
        delay=float(parametros.get("delay", 1.0)),
    )
