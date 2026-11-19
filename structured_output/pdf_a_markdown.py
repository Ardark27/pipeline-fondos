"""Transformación de los PDF descargados (KID y fichas) a Markdown con PyMuPDF.

Usa pymupdf4llm, que conserva la estructura del documento (títulos, listas y tablas)
y aplica OCR (RapidOCR o Tesseract, el que esté instalado) en las páginas que lo necesitan.

Uso:
    python pdf_a_markdown.py                         # todos los PDF de descargas/bestinver
    python pdf_a_markdown.py ruta/al/fichero.pdf     # un fichero
    python pdf_a_markdown.py ruta/carpeta --salida markdown/bestinver
    python pdf_a_markdown.py --ocr siempre           # fuerza el OCR en todas las páginas
"""

import argparse
import sys
from pathlib import Path

import pymupdf4llm

RAIZ_REPO = Path(__file__).resolve().parent.parent
ENTRADA_POR_DEFECTO = RAIZ_REPO / "descargas" / "bestinver"

# Modos de OCR de la línea de comandos -> argumentos de pymupdf4llm.to_markdown
MODOS_OCR = {
    "auto": {"use_ocr": True, "force_ocr": False},  # OCR solo en las páginas que lo necesitan
    "siempre": {"use_ocr": True, "force_ocr": True},
    "nunca": {"use_ocr": False, "force_ocr": False},
}


def pdf_a_markdown(ruta_pdf: Path, modo_ocr: str = "auto", idioma: str = "spa") -> str:
    """Convierte un PDF a texto Markdown."""
    return pymupdf4llm.to_markdown(
        str(ruta_pdf),
        ocr_language=idioma,
        show_progress=False,
        **MODOS_OCR[modo_ocr],
    )


def buscar_pdfs(entradas: list[Path]) -> list[Path]:
    """Devuelve los PDF de las rutas dadas (ficheros o carpetas, sin recursión)."""
    pdfs = []
    for entrada in entradas:
        if entrada.is_dir():
            pdfs.extend(sorted(entrada.glob("*.pdf")))
        elif entrada.suffix.lower() == ".pdf" and entrada.is_file():
            pdfs.append(entrada)
        else:
            print(f"AVISO: se ignora '{entrada}' (no es un PDF ni una carpeta)")
    return pdfs


def main() -> int:
    parser = argparse.ArgumentParser(description="Convierte PDF de fondos a Markdown con PyMuPDF.")
    parser.add_argument(
        "entradas",
        nargs="*",
        type=Path,
        default=[ENTRADA_POR_DEFECTO],
        help=f"PDF o carpetas con PDF (por defecto {ENTRADA_POR_DEFECTO.relative_to(RAIZ_REPO)})",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        help="Carpeta donde guardar los .md (por defecto, junto a cada PDF)",
    )
    parser.add_argument("--ocr", choices=MODOS_OCR, default="auto", help="Uso del OCR (por defecto auto)")
    parser.add_argument("--idioma", default="spa", help="Idioma del OCR para Tesseract (por defecto spa)")
    parser.add_argument(
        "--sobrescribir", action="store_true", help="Regenera los .md aunque ya existan"
    )
    args = parser.parse_args()

    pdfs = buscar_pdfs(args.entradas)
    if not pdfs:
        print("No se ha encontrado ningún PDF.")
        return 1
    if args.salida:
        args.salida.mkdir(parents=True, exist_ok=True)

    convertidos, omitidos, fallos = [], [], []
    for i, pdf in enumerate(pdfs, 1):
        destino = (args.salida or pdf.parent) / f"{pdf.stem}.md"
        if destino.exists() and not args.sobrescribir:
            print(f"[{i}/{len(pdfs)}] {pdf.name}: ya existe {destino.name}, se omite")
            omitidos.append(pdf)
            continue
        print(f"[{i}/{len(pdfs)}] {pdf.name} -> {destino}")
        try:
            destino.write_text(pdf_a_markdown(pdf, args.ocr, args.idioma), encoding="utf-8")
            convertidos.append(pdf)
        except Exception as error:  # un PDF corrupto no debe parar el resto
            print(f"    ERROR: {error}")
            fallos.append((pdf, error))

    print("\nResumen:")
    print(f"  Convertidos: {len(convertidos)}")
    print(f"  Omitidos (ya existían): {len(omitidos)}")
    print(f"  Fallos: {len(fallos)}")
    for pdf, error in fallos:
        print(f"    - {pdf.name}: {error}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
