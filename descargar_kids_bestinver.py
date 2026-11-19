"""
Descarga los documentos "Datos fundamentales" (KID) y "Ficha del fondo"
de todos los fondos de inversión de Bestinver y los guarda en S3.

Flujo:
  1. Abre https://www.bestinver.es/fondos-de-inversion/ y lee la lista de
     fondos del footer (XPath /html/body/div[1]/footer/div[2]/div/div[1]/div/ul).
  2. Entra en la página de cada fondo y lee la lista de documentos
     (XPath /html/body/div[1]/div/main/section[4]/div[1]/div[2]/ul).
  3. Descarga los documentos cuyo texto coincide con los buscados y los sube
     a s3://<bucket>/<prefijo>/<AAAAMMDD>/<slug>_<tipo>.pdf.

Las credenciales de AWS se toman de la configuración estándar
(aws configure / aws login, variables de entorno o perfil con AWS_PROFILE).

Uso:
    python descargar_kids_bestinver.py [--bucket curso-miax-pipeline-fondos]
                                       [--prefijo bestinver] [--fecha AAAAMMDD]
                                       [--delay 1.0]
"""

import argparse
import re
import time
import unicodedata
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from lxml import html

BASE_URL = "https://www.bestinver.es/fondos-de-inversion/"

BUCKET_POR_DEFECTO = "curso-miax-pipeline-fondos"
PREFIJO_POR_DEFECTO = "bestinver"

XPATH_LISTA_FONDOS = "/html/body/div[1]/footer/div[2]/div/div[1]/div/ul"
XPATH_LISTA_DOCUMENTOS = "/html/body/div[1]/div/main/section[4]/div[1]/div[2]/ul"

# Texto del enlace (normalizado) -> sufijo del fichero descargado
DOCUMENTOS_OBJETIVO = {
    "datos fundamentales": "datos_fundamentales",
    "ficha del fondo": "ficha_fondo",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def obtener_arbol(session: requests.Session, url: str) -> html.HtmlElement:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def obtener_fondos(session: requests.Session) -> list[tuple[str, str]]:
    """Devuelve [(nombre, url)] de los fondos listados en el footer."""
    arbol = obtener_arbol(session, BASE_URL)
    listas = arbol.xpath(XPATH_LISTA_FONDOS)
    if listas:
        enlaces = listas[0].xpath(".//a[@href]")
    else:
        # Respaldo por si cambia la maquetación: enlaces del footer a /fondos-de-inversion/<slug>/
        print("[aviso] XPath de la lista de fondos no encontrado, usando respaldo.")
        enlaces = arbol.xpath("//footer//a[contains(@href, '/fondos-de-inversion/')]")

    fondos, vistos = [], set()
    for a in enlaces:
        url = urljoin(BASE_URL, a.get("href"))
        nombre = " ".join(a.text_content().split())
        # Solo páginas concretas de fondo (/fondos-de-inversion/<slug>/)
        partes = [p for p in urlparse(url).path.split("/") if p]
        if len(partes) != 2 or partes[0] != "fondos-de-inversion":
            continue
        if url not in vistos:
            vistos.add(url)
            fondos.append((nombre, url))
    return fondos


def obtener_documentos(session: requests.Session, url_fondo: str) -> dict[str, str]:
    """Devuelve {sufijo: url_pdf} con los documentos objetivo del fondo."""
    arbol = obtener_arbol(session, url_fondo)
    listas = arbol.xpath(XPATH_LISTA_DOCUMENTOS)
    if listas:
        enlaces = listas[0].xpath(".//a[@href]")
    else:
        # Respaldo: cualquier enlace a PDF de la página
        print("    [aviso] XPath de documentos no encontrado, usando respaldo.")
        enlaces = arbol.xpath("//main//a[contains(@href, '.pdf')]")

    encontrados = {}
    for a in enlaces:
        texto = normalizar(a.text_content())
        for objetivo, sufijo in DOCUMENTOS_OBJETIVO.items():
            if texto == objetivo and sufijo not in encontrados:
                encontrados[sufijo] = urljoin(url_fondo, a.get("href"))
    return encontrados


def descargar(session: requests.Session, url: str) -> bytes:
    """Descarga el PDF completo en memoria (son ficheros pequeños)."""
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def subir_s3(s3, bucket: str, clave: str, contenido: bytes, url_origen: str) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=clave,
        Body=contenido,
        ContentType="application/pdf",
        Metadata={"url-origen": url_origen},
    )


def fecha_valida(texto: str) -> str:
    """Valida el formato AAAAMMDD para argparse."""
    try:
        datetime.strptime(texto, "%Y%m%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"fecha no válida '{texto}', formato AAAAMMDD")
    return texto


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bucket", default=BUCKET_POR_DEFECTO, help="Bucket de S3 de destino")
    parser.add_argument("--prefijo", default=PREFIJO_POR_DEFECTO, help="Carpeta raíz dentro del bucket")
    parser.add_argument(
        "--fecha", type=fecha_valida, default=date.today().strftime("%Y%m%d"),
        help="Subcarpeta de fecha AAAAMMDD (por defecto, hoy)",
    )
    parser.add_argument("--delay", type=float, default=1.0, help="Segundos de espera entre peticiones")
    args = parser.parse_args()

    carpeta_s3 = f"{args.prefijo.strip('/')}/{args.fecha}"
    s3 = boto3.client("s3")
    try:
        s3.head_bucket(Bucket=args.bucket)
    except (BotoCoreError, ClientError) as e:
        raise SystemExit(f"[error] no se puede acceder al bucket '{args.bucket}': {e}")
    print(f"Destino: s3://{args.bucket}/{carpeta_s3}/\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    fondos = obtener_fondos(session)
    print(f"Encontrados {len(fondos)} fondos.\n")

    total, fallos = 0, []
    for nombre, url in fondos:
        slug = [p for p in urlparse(url).path.split("/") if p][-1]
        print(f"- {nombre} ({url})")
        time.sleep(args.delay)
        try:
            docs = obtener_documentos(session, url)
        except requests.RequestException as e:
            print(f"    [error] no se pudo abrir la página: {e}")
            fallos.append((nombre, "página"))
            continue

        for sufijo in DOCUMENTOS_OBJETIVO.values():
            if sufijo not in docs:
                print(f"    [sin documento] {sufijo}")
                continue
            clave = f"{carpeta_s3}/{slug}_{sufijo}.pdf"
            try:
                time.sleep(args.delay)
                contenido = descargar(session, docs[sufijo])
            except requests.RequestException as e:
                print(f"    [error] descarga {sufijo}: {e}")
                fallos.append((nombre, f"{sufijo} (descarga)"))
                continue
            try:
                subir_s3(s3, args.bucket, clave, contenido, docs[sufijo])
                print(f"    [ok] s3://{args.bucket}/{clave}")
                total += 1
            except (BotoCoreError, ClientError) as e:
                print(f"    [error] subida {sufijo}: {e}")
                fallos.append((nombre, f"{sufijo} (subida S3)"))

    print(f"\nSubidos {total} documentos a 's3://{args.bucket}/{carpeta_s3}/'.")
    if fallos:
        print(f"Fallos ({len(fallos)}):")
        for nombre, que in fallos:
            print(f"  - {nombre}: {que}")


if __name__ == "__main__":
    main()
