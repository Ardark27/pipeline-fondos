# pipeline-fondos

Proyecto para extraer información de los KID (Documento de Datos Fundamentales) y fichas de fondos de inversión.

El pipeline tiene tres etapas y todas leen y escriben en **Amazon S3** (bucket `curso-miax-pipeline-fondos`):

1. Descarga, mediante web scraping, los documentos de los fondos de **Bestinver** (PDF).
2. Convierte los PDF a Markdown.
3. Extrae los datos del KID con un LLM y los guarda en JSON.

### Estructura del bucket

Cada etapa tiene su carpeta raíz y dentro mantiene la misma ruta `<gestora>/<AAAAMMDD>/<slug>_<tipo>`:

```
s3://curso-miax-pipeline-fondos/
├── download/                                    # etapa 1: PDF descargados
│   └── bestinver/20261119/bestinfond_datos_fundamentales.pdf
├── markdown/                                    # etapa 2: PDF convertidos a Markdown
│   └── bestinver/20261119/bestinfond_datos_fundamentales.md
└── extraction/                                  # etapa 3: datos extraídos del KID
    └── bestinver/20261119/bestinfond_datos_fundamentales.json
```

### Estructura del repositorio

```
common/almacenamiento_s3.py          # código compartido: rutas del bucket y lectura/escritura en S3
webscrapper/descargar_kids_bestinver.py   # etapa 1: descarga
pdf_markdown/pdf_a_markdown.py       # etapa 2: PDF -> Markdown
structured_output/extractor_kid.py   # etapa 3: extracción del KID
```

Todas las etapas importan `common` (cada script añade la raíz del repo al `sys.path`, así que se pueden ejecutar directamente con `python <carpeta>/<script>.py`).

## Instalación

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

Dependencias principales: `requests` (peticiones HTTP), `lxml` (parseo HTML y XPath), `boto3[crt]` (subida a S3; el extra `crt` es necesario si las credenciales se obtienen con `aws login`), `pymupdf4llm` + `rapidocr` + `onnxruntime` (PDF → Markdown con OCR) y `langchain-aws` (extracción con un LLM en Bedrock).

### Credenciales de AWS

El script usa la cadena de credenciales estándar de AWS: `aws login` / `aws configure`, variables de entorno (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) o un perfil con `AWS_PROFILE`. La cuenta necesita permisos `s3:PutObject`, `s3:GetObject` y `s3:ListBucket` sobre el bucket `curso-miax-pipeline-fondos`.

## Etapa 1: descarga de documentos de Bestinver

Script: [`webscrapper/descargar_kids_bestinver.py`](webscrapper/descargar_kids_bestinver.py)

```bash
python webscrapper/descargar_kids_bestinver.py                       # sube a s3://curso-miax-pipeline-fondos/download/bestinver/<hoy>/
python webscrapper/descargar_kids_bestinver.py --fecha 20261119      # fuerza la carpeta de fecha (AAAAMMDD)
python webscrapper/descargar_kids_bestinver.py --bucket otro-bucket  # bucket distinto
python webscrapper/descargar_kids_bestinver.py --prefijo pruebas     # carpeta de gestora distinta dentro de download/
python webscrapper/descargar_kids_bestinver.py --delay 0.5           # segundos entre peticiones (por defecto 1.0)
```

### Cómo se analizó la web

1. **Listado de fondos.** En `https://www.bestinver.es/fondos-de-inversion/` el pie de página contiene una lista con todos los productos. La lista de fondos de inversión está en el XPath:

   ```
   /html/body/div[1]/footer/div[2]/div/div[1]/div/ul
   ```

   Cada enlace lleva a la página del fondo: `/fondos-de-inversion/<slug>/`.

2. **Documentos de cada fondo.** En la página de cada fondo hay una lista de documentos (datos fundamentales, ficha, folleto, reglamento, cuentas anuales, informes semestrales...) en el XPath:

   ```
   /html/body/div[1]/div/main/section[4]/div[1]/div[2]/ul
   ```

   Los enlaces apuntan directamente a PDFs en `/wp-content/uploads/`, por ejemplo
   `bestinfond_fi_datos_fundamentales.pdf`.

3. **Documentos que se descargan:** solo **"Datos fundamentales"** (KID) y **"Ficha del fondo"**.

Las páginas son HTML estático (no necesitan JavaScript), así que basta con `requests` + `lxml`; no hace falta Selenium ni Playwright.

### Qué hace el script

1. Descarga la página de listado y extrae los enlaces de la lista del footer (XPath anterior). Se queda solo con URLs del tipo `/fondos-de-inversion/<slug>/`.
2. Para cada fondo, abre su página, localiza la lista de documentos y selecciona los enlaces cuyo texto (normalizado: minúsculas, sin acentos) es exactamente `datos fundamentales` o `ficha del fondo`.
3. Comprueba al inicio que el bucket es accesible (si no, termina con error).
4. Descarga cada PDF en memoria y lo sube a S3 con `ContentType: application/pdf` y la URL original en los metadatos (`x-amz-meta-url-origen`). Si se relanza el mismo día, los objetos se sobrescriben.
5. Muestra un resumen con los documentos descargados y los fallos.

**Respaldo:** si un XPath deja de encontrar nada (porque cambie la maquetación de la web), el script usa un selector más general (enlaces del footer a `/fondos-de-inversion/` o enlaces a `.pdf` dentro de `<main>`) y muestra un aviso.

### Salida

```
s3://curso-miax-pipeline-fondos/
└── download/
    └── bestinver/
        └── 20261119/
            ├── bestinfond_datos_fundamentales.pdf
            ├── bestinfond_ficha_fondo.pdf
            ├── bestinver-internacional_datos_fundamentales.pdf
            └── ...
```

Cada ejecución guarda los documentos en una carpeta con la fecha (`AAAAMMDD`), así se conserva el histórico de versiones de los KID. Nombre de cada fichero: `<slug-del-fondo>_<tipo>.pdf`.

### Resultados (ejecución del 19/11/2026)

- 24 enlaces en el footer, 22 de ellos fondos con documentos.
- **37 PDFs** subidos a `s3://curso-miax-pipeline-fondos/download/bestinver/20261119/` (se subieron inicialmente a `bestinver/20261119/` y se copiaron a `download/` al cambiar la estructura): 22 "Datos fundamentales" y 15 "Fichas del fondo".
- Sin ficha publicada en la web: Latam, Solidario y Bonos Institucional I–V.
- `Otros` y `SICAV Luxemburguesas` son páginas que agrupan varios productos y no tienen estos documentos.

## Etapa 2: transformación de PDF a Markdown

Script: [`pdf_markdown/pdf_a_markdown.py`](pdf_markdown/pdf_a_markdown.py)

Convierte los PDF a Markdown con [PyMuPDF](https://pymupdf.readthedocs.io/) (`pymupdf4llm`), que conserva títulos, listas y **tablas** (las de costes y rentabilidades salen como tablas Markdown) y aplica **OCR** con RapidOCR en las páginas que lo necesitan. RapidOCR se instala con `pip` y no requiere nada más en el sistema; si no está, `pymupdf4llm` usa Tesseract si lo encuentra instalado.

Lee los PDF de `download/<gestora>/<AAAAMMDD>/` y sube cada `<slug>_<tipo>.pdf` como `markdown/<gestora>/<AAAAMMDD>/<slug>_<tipo>.md` (`ContentType: text/markdown`, con la clave del PDF en `x-amz-meta-pdf-origen`). No guarda nada en local.

```bash
python pdf_markdown/pdf_a_markdown.py                                  # todos los PDF de la última fecha de download/bestinver/
python pdf_markdown/pdf_a_markdown.py --fecha 20261119                 # una fecha concreta
python pdf_markdown/pdf_a_markdown.py bestinfond_datos_fundamentales.pdf   # solo esos ficheros de la carpeta
python pdf_markdown/pdf_a_markdown.py --prefijo otra-gestora --bucket otro-bucket
python pdf_markdown/pdf_a_markdown.py --ocr siempre                    # auto (por defecto) | siempre | nunca
python pdf_markdown/pdf_a_markdown.py --sobrescribir                   # regenera los .md que ya existan en S3
```

Si no se indica `--fecha`, usa la carpeta de fecha más reciente de `download/<gestora>/`. Los `.md` que ya existen en S3 se omiten salvo con `--sobrescribir`. Termina con un resumen de convertidos, omitidos y fallos. El OCR tarda unos segundos por página.

## Etapa 3: extracción de datos del KID

Script: [`structured_output/extractor_kid.py`](structured_output/extractor_kid.py)

Lee el Markdown de un KID de `markdown/<gestora>/<AAAAMMDD>/` (generado en la etapa 2) y extrae con un LLM en Amazon Bedrock (salida estructurada con Pydantic) el ISIN, nombre, gestora, SRI, periodo de mantenimiento y costes, cada uno con su **evidencia** literal. Después comprueba que cada evidencia aparece en el documento (ignorando la marca Markdown y los espacios) y sube el resultado a `extraction/<gestora>/<AAAAMMDD>/<slug>_datos_fundamentales.json`.

```bash
python structured_output/extractor_kid.py                              # KID de Bestinfond, última fecha de markdown/bestinver/
python structured_output/extractor_kid.py bestinver-renta bestvalue    # KID de esos fondos (slugs)
python structured_output/extractor_kid.py --todos                      # todos los *_datos_fundamentales.md de la carpeta
python structured_output/extractor_kid.py --fecha 20261119             # una fecha concreta
```

Admite también `--bucket` y `--prefijo`. Formato del JSON:

```json
{
  "markdown_origen": "markdown/bestinver/20261119/bestinfond_datos_fundamentales.md",
  "modelo": "global.moonshotai.kimi-k3.1",
  "datos": { "isin": "ES0114673033", "isin_evidencia": "ISIN: ES0114673033", "sri": 4, "...": "..." },
  "verificacion_evidencias": { "isin": true, "sri": true, "...": true }
}
```

## Ejecución en AWS Lambda

Cada etapa se empaqueta en su propia imagen Docker (basada en `dockerfile_template`) y se despliega como una función Lambda:

| Etapa | Dockerfile | Función Lambda | Imagen en ECR (`823028065899.dkr.ecr.eu-west-3.amazonaws.com/...`) |
|---|---|---|---|
| 1. Descarga | `webscrapper/Dockerfile` | `pipeline-fondos-descarga` | `webscrapper-miax-14:<sha>` |
| 2. PDF → Markdown | `pdf_markdown/Dockerfile` | `pipeline-fondos-markdown` | `pdf-to-markdown-miax-14:<sha>` |
| 3. Extracción | `structured_output/Dockerfile` | `pipeline-fondos-extraccion` | `structured-output-miax-14:<sha>` |

Cada carpeta de etapa contiene:

- `Dockerfile`: copia `common/`, el script de la etapa y `app.py` en `${LAMBDA_TASK_ROOT}`. Se construye **desde la raíz del repo** (para poder copiar `common/`): `docker build -f pdf_markdown/Dockerfile .`
- `requirements.txt`: solo las dependencias de esa etapa, para que la imagen sea más pequeña. El `requirements.txt` de la raíz sigue siendo el del entorno local.
- `app.py`: `handler(event, context)`, que lee los parámetros del evento y llama directamente a la función de la etapa.

Cada script separa la lógica de la etapa en una función con parámetros normales; su `main()` solo lee la línea de comandos y la llama, igual que hace el `handler` con el evento:

| Etapa | Función | Claves del evento (todas opcionales) |
|---|---|---|
| 1 | `descargar_documentos(bucket, prefijo, fecha, delay)` | `bucket`, `prefijo`, `fecha` (por defecto hoy), `delay` |
| 2 | `convertir_pdfs(bucket, prefijo, fecha, ficheros, modo_ocr, idioma, sobrescribir)` | `bucket`, `prefijo`, `fecha`, `ficheros`, `ocr`, `idioma`, `sobrescribir` |
| 3 | `extraer_kids(bucket, prefijo, fecha, fondos, todos)` | `bucket`, `prefijo`, `fecha`, `fondos`, `todos` |

Los valores por defecto son los mismos que en la línea de comandos. Ejemplos:

```jsonc
{"fecha": "20261119"}                                                    // etapa 1
{"fecha": "20261119", "ocr": "auto", "sobrescribir": true,
 "ficheros": ["bestinfond_datos_fundamentales.pdf"]}                      // etapa 2
{"todos": true}                                                          // etapa 3: o "fondos": ["bestinver-renta"]
```

La Lambda devuelve el resumen que devuelve la función: carpetas, fecha usada, claves de S3 generadas (`subidos` / `convertidos` y `omitidos` / `extraidos`) y `fallos`. Los fallos de documentos sueltos no hacen fallar la invocación (el detalle queda en el resumen y en CloudWatch Logs). Un error que impide ejecutar la etapa sí la hace fallar: `ErrorEtapa` (bucket inaccesible, no hay carpeta de fecha o nada que procesar) o `ValueError` (fecha o modo de OCR no válidos). Por consola, esos mismos errores se muestran y el script termina con código 1.

### Despliegue (GitHub Actions)

El workflow [`.github/workflows/deploy_lambda.yaml`](.github/workflows/deploy_lambda.yaml) se ejecuta en cada push a `main` (o a mano con *Run workflow*) y tiene dos jobs:

1. **Detectar etapas cambiadas** (`cambios`): compara el commit anterior al push con el nuevo (`git diff --name-only`) y decide qué etapas desplegar:
   - un cambio dentro de la carpeta de una etapa (`webscrapper/`, `pdf_markdown/`, `structured_output/`) despliega solo esa etapa; si cambian varias, se despliegan esas;
   - un cambio en `common/` despliega **todas**, porque las tres imágenes lo incluyen;
   - un cambio en otros ficheros (README, `CLAUDE.md`, `requirements.txt` de la raíz...) no despliega nada;
   - si no hay con qué comparar (ejecución a mano, primer push o push forzado), se despliegan todas.
2. **Deploy** (`deploy`): con una matriz con las etapas seleccionadas, construye cada imagen, la sube a ECR y actualiza el código de su Lambda. Si no hay etapas seleccionadas, no se ejecuta.

Se autentica en AWS por OIDC con el rol `miax-github-deploy`. La lista de etapas (carpeta, repositorio ECR y función Lambda) está en la variable `ETAPAS` del job `cambios`; una etapa nueva se añade ahí.

Requisitos en AWS (región `eu-west-3`), creados previamente:

- Repositorios ECR `webscrapper-miax-14`, `pdf-to-markdown-miax-14` y `structured-output-miax-14` (uno por etapa; cada imagen se etiqueta con el SHA del commit).
- Las tres funciones Lambda de tipo imagen, con un rol con permisos de S3 sobre el bucket (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`) y, en la etapa 3, `bedrock:InvokeModel`.
- Timeout y memoria suficientes: la etapa 2 (OCR) es la más pesada; el máximo de Lambda son 15 minutos, así que con muchos PDF conviene lanzarla por `ficheros` o con varias invocaciones.

## Próximas etapas

- [x] Extraer información de los KID descargados (PDF → Markdown → datos estructurados).
- [x] Leer los PDF de S3 y guardar los Markdown y los datos extraídos en S3.
- [ ] Añadir otras gestoras.
