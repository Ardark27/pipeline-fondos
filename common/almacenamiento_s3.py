"""Utilidades comunes para leer y escribir en S3 las distintas etapas del pipeline.

Estructura del bucket (misma ruta <gestora>/<AAAAMMDD>/<slug>_<tipo> en cada etapa):

    download/<gestora>/<AAAAMMDD>/<slug>_<tipo>.pdf     etapa 1: PDF descargados
    markdown/<gestora>/<AAAAMMDD>/<slug>_<tipo>.md      etapa 2: PDF convertidos a Markdown
    extraction/<gestora>/<AAAAMMDD>/<slug>_<tipo>.json  etapa 3: datos extraídos
"""

import argparse
import re
from datetime import datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError

BUCKET_POR_DEFECTO = "curso-miax-pipeline-fondos"
PREFIJO_POR_DEFECTO = "bestinver"

CARPETA_DESCARGA = "download"
CARPETA_MARKDOWN = "markdown"
CARPETA_EXTRACCION = "extraction"


class ErrorEtapa(RuntimeError):
    """Error que impide ejecutar una etapa (bucket inaccesible, nada que procesar...).

    Los scripts lo muestran y terminan con código 1; en Lambda hace fallar la invocación.
    """


def comprobar_fecha(texto: str) -> str:
    """Devuelve la fecha si tiene el formato AAAAMMDD; si no, lanza ValueError."""
    try:
        datetime.strptime(texto, "%Y%m%d")
    except (TypeError, ValueError):
        raise ValueError(f"fecha no válida '{texto}', formato AAAAMMDD")
    return texto


def fecha_valida(texto: str) -> str:
    """Valida el formato AAAAMMDD para argparse."""
    try:
        return comprobar_fecha(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def carpeta(etapa: str, prefijo: str, fecha: str) -> str:
    """Ruta de la carpeta de una etapa, sin barra final: <etapa>/<prefijo>/<fecha>."""
    return f"{etapa}/{prefijo.strip('/')}/{fecha}"


def conectar(bucket: str):
    """Crea el cliente de S3 y comprueba que el bucket es accesible (si no, lanza ErrorEtapa)."""
    s3 = boto3.client("s3")
    try:
        s3.head_bucket(Bucket=bucket)
    except (BotoCoreError, ClientError) as e:
        raise ErrorEtapa(f"no se puede acceder al bucket '{bucket}': {e}") from e
    return s3


def listar_claves(s3, bucket: str, carpeta_s3: str, extension: str) -> list[str]:
    """Claves de la carpeta (sin recursión) que terminan en la extensión dada, ordenadas."""
    claves = []
    paginador = s3.get_paginator("list_objects_v2")
    for pagina in paginador.paginate(Bucket=bucket, Prefix=f"{carpeta_s3}/", Delimiter="/"):
        for obj in pagina.get("Contents", []):
            if obj["Key"].lower().endswith(extension):
                claves.append(obj["Key"])
    return sorted(claves)


def ultima_fecha(s3, bucket: str, etapa: str, prefijo: str) -> str | None:
    """Fecha (AAAAMMDD) más reciente con carpeta en <etapa>/<prefijo>/, o None si no hay."""
    fechas = []
    paginador = s3.get_paginator("list_objects_v2")
    raiz = f"{etapa}/{prefijo.strip('/')}/"
    for pagina in paginador.paginate(Bucket=bucket, Prefix=raiz, Delimiter="/"):
        for comun in pagina.get("CommonPrefixes", []):
            nombre = comun["Prefix"][len(raiz):].strip("/")
            if re.fullmatch(r"\d{8}", nombre):
                fechas.append(nombre)
    return max(fechas) if fechas else None


def leer(s3, bucket: str, clave: str) -> bytes:
    return s3.get_object(Bucket=bucket, Key=clave)["Body"].read()


def existe(s3, bucket: str, clave: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=clave)
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def escribir(s3, bucket: str, clave: str, contenido: bytes, content_type: str, metadatos: dict | None = None) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=clave,
        Body=contenido,
        ContentType=content_type,
        Metadata=metadatos or {},
    )


def resolver_fecha(s3, bucket: str, etapa: str, prefijo: str, fecha: str | None) -> str:
    """Devuelve la fecha indicada o, si no se indica, la más reciente disponible en la etapa."""
    if fecha:
        return comprobar_fecha(fecha)
    fecha = ultima_fecha(s3, bucket, etapa, prefijo)
    if not fecha:
        raise ErrorEtapa(f"no hay ninguna carpeta de fecha en s3://{bucket}/{etapa}/{prefijo}/")
    return fecha
