# CLAUDE.md

Guía para Claude Code en este repositorio.

## Proyecto

Pipeline para descargar y extraer información de los KID (Documento de Datos Fundamentales) y fichas de fondos de inversión. Proyecto del curso MIAX 2026. Ver `README.md` para el detalle de cada etapa.

## Entorno

- Windows, Python 3.14, entorno virtual en `venv/` (no se versiona).
- Dependencias en `requirements.txt`. Si añades una librería, añádela ahí.
- Ejecutar scripts desde la raíz del repo: `python <carpeta>/<script>.py`. Los scripts añaden la raíz al `sys.path` para importar `common`.

## Estructura

- `common/almacenamiento_s3.py`: código compartido (rutas del bucket, lectura/escritura en S3). Todo acceso a S3 pasa por aquí.
- `webscrapper/descargar_kids_bestinver.py`: etapa 1, scraping de los PDFs de Bestinver (datos fundamentales y ficha del fondo).
- `pdf_markdown/pdf_a_markdown.py`: etapa 2, conversión de PDF a Markdown.
- `structured_output/extractor_kid.py`: etapa 3, extracción de datos del KID con un LLM.
- Lambda: cada carpeta de etapa tiene `Dockerfile` (se construye desde la raíz: `docker build -f <carpeta>/Dockerfile .`), `requirements.txt` propio y `app.py` con el `handler`, que llama directamente a la función de la etapa (`descargar_documentos`, `convertir_pdfs`, `extraer_kids`). Cada script mantiene esa lógica en una función con parámetros que devuelve un resumen (dict serializable a JSON), y `main()` solo hace el argparse y la llama. Los errores que paran una etapa se lanzan como `alm.ErrorEtapa` (no `SystemExit`). Las etapas se encadenan: el resumen siempre incluye `bucket`, `prefijo`, `fecha`, `claves` (claves de S3 que deja listas para la siguiente) y `fallos`, cada etapa acepta `claves` de la anterior como entrada, y el `handler` lee el evento con `alm.evento_lambda(event)`. Si una etapa añade un parámetro, añádelo a la función, al argparse y al `handler`; si añade una librería, también al `requirements.txt` de la etapa.
- Infraestructura: **toda** la infraestructura de AWS se gestiona con Terraform en `terraform/` (no crear ni cambiar recursos a mano ni con la CLI). Las etapas están en `local.etapas` (`terraform/etapas.tf`, clave = carpeta de la etapa); la máquina de Step Functions que las encadena, en `terraform/step_functions.tf`. Una etapa nueva se añade en ambos. Los roles y políticas se nombran `pipeline-fondos-*` (el rol de despliegue solo tiene permisos IAM sobre ese prefijo). La etiqueta de cada imagen la genera `terraform/etiquetas_imagen.sh` (SHA del último commit que cambió la carpeta de la etapa o `common/`). El workflow `.github/workflows/deploy.yaml` crea los repositorios ECR, construye las imágenes que faltan y hace `terraform apply`. Comprobar los cambios con `terraform fmt`, `terraform validate` y `terraform plan`; no hacer `apply` salvo que se pida.
- Almacenamiento: los PDFs se suben a S3, bucket `curso-miax-pipeline-fondos`, con claves `download/<gestora>/<AAAAMMDD>/<slug>_<tipo>.pdf`; los Markdown van a `markdown/...` (`.md`) y los JSON extraídos a `extraction/...` (`.json`), con la misma ruta (`boto3`, credenciales estándar de AWS). `descargas/` queda en `.gitignore` por si se guarda algo en local.

## Convenciones

- Código, comentarios, mensajes de consola y documentación en **español**.
- Scraping: `requests` + `lxml` con XPath mientras las webs sean HTML estático. Solo usar Selenium/Playwright si la página necesita JavaScript.
- Cada scraper:
  - usa los XPath encontrados en la web como selector principal, con un selector más general de respaldo que avisa por consola;
  - identifica los documentos por el texto del enlace normalizado (minúsculas, sin acentos);
  - deja una pausa entre peticiones (`--delay`) y envía un User-Agent de navegador;
  - sube los ficheros a S3 y acepta `--bucket`, `--prefijo` (por defecto, la gestora) y `--fecha` (AAAAMMDD, por defecto hoy);
  - nombra los ficheros `<slug-del-fondo>_<tipo>.pdf`;
  - termina con un resumen de subidas y fallos.
- Una nueva gestora va en su propio script `webscrapper/descargar_kids_<gestora>.py` y se documenta en el README como una sección nueva.

## Al terminar un cambio

- Actualizar `README.md` si cambia el uso, la salida o se añade una etapa.
- No hacer commit salvo que se pida.
