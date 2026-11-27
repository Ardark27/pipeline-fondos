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
terraform/                           # infraestructura de AWS (S3, ECR, Lambda, Step Functions, Scheduler, IAM)
.github/workflows/deploy.yaml        # despliegue: imágenes a ECR + terraform apply
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
python pdf_markdown/pdf_a_markdown.py --claves download/bestinver/20261119/bestinfond_ficha_fondo.pdf  # por clave de S3
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
python structured_output/extractor_kid.py --claves markdown/bestinver/20261119/bestinfond_datos_fundamentales.md
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

Cada etapa se empaqueta en su propia imagen Docker y se despliega como una función Lambda (la infraestructura se gestiona con Terraform, ver [Infraestructura](#infraestructura-terraform)):

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
| 1 | `descargar_documentos(bucket, prefijo, fecha, delay)` | `bucket`, `prefijo`, `fecha` (por defecto, el día de `time` o hoy), `delay`, `time` (hora programada del scheduler) |
| 2 | `convertir_pdfs(bucket, prefijo, fecha, ficheros, modo_ocr, idioma, sobrescribir, claves)` | `bucket`, `prefijo`, `fecha`, `ficheros` o `claves`, `ocr`, `idioma`, `sobrescribir` |
| 3 | `extraer_kids(bucket, prefijo, fecha, fondos, todos, claves)` | `bucket`, `prefijo`, `fecha`, `fondos`/`todos` o `claves` |

Los valores por defecto son los mismos que en la línea de comandos. Ejemplos:

```jsonc
{"fecha": "20261119"}                                                    // etapa 1
{"fecha": "20261119", "ocr": "auto", "sobrescribir": true,
 "ficheros": ["bestinfond_datos_fundamentales.pdf"]}                      // etapa 2
{"todos": true}                                                          // etapa 3: o "fondos": ["bestinver-renta"]
```

La Lambda devuelve el resumen que devuelve la función. Todas las etapas comparten estas claves (más detalle propio, como `convertidos` y `omitidos` en la etapa 2):

```jsonc
{"bucket": "curso-miax-pipeline-fondos", "prefijo": "bestinver", "fecha": "20261119",
 "claves": ["download/bestinver/20261119/bestinfond_datos_fundamentales.pdf", "..."],  // lo que deja listo la etapa
 "fallos": []}
```

### Ejecución programada (EventBridge Scheduler)

El schedule `descarga-bestinver-fondos` de **EventBridge Scheduler** (`cron(0 9 15 * ? *)`, zona horaria `Europe/Madrid`: el día 15 de cada mes a las 9:00) lanza la máquina de Step Functions `pipeline-fondos` (abajo) con este **Input**:

```json
{"time": "<aws.scheduler.scheduled-time>", "prefijo": "bestinver"}
```

Scheduler sustituye `<aws.scheduler.scheduled-time>` por la hora programada (ISO 8601 en UTC) y el handler de la etapa 1 toma la carpeta de fecha del **día UTC de esa hora**, no del reloj: si el scheduler reintenta, escribe en la misma carpeta. Si el evento trae `fecha`, manda `fecha`. La expresión, la zona horaria y la gestora son variables de Terraform (`programacion`, `zona_horaria`, `gestora`).

El handler de la etapa 1 también acepta el evento de una regla programada de EventBridge (`"detail-type": "Scheduled Event"`, con `time`): sus parámetros, si los hay, van en `detail`.

### Encadenamiento de etapas

La salida de cada etapa es un evento válido para la siguiente: con `claves`, la etapa 2 convierte solo los PDF que acaba de subir la etapa 1 (no toda la carpeta) y la etapa 3 extrae solo los KID de los `.md` de la etapa 2 (convertidos y omitidos; las fichas se ignoran). `claves` no se combina con `ficheros` (etapa 2) ni con `fondos`/`todos` (etapa 3). Si `claves` llega vacía, la etapa falla con `ErrorEtapa` (no hay nada que procesar). Los handlers aceptan el evento directo (invocación manual o Step Functions) o el sobre de Lambda Destinations (`{"responsePayload": ...}`), con `alm.evento_lambda`.

En AWS las encadena la máquina de estados **`pipeline-fondos`** (Step Functions con JSONata, definida en [`terraform/step_functions.tf`](terraform/step_functions.tf)):

```
Descarga ──> Markdown (Map: una invocación por PDF, hasta 5 a la vez) ──> Extraccion
```

- `Descarga` invoca la etapa 1 con la entrada de la ejecución.
- `Markdown` recorre las `claves` de la etapa 1 e invoca la etapa 2 con **un PDF por invocación** (así ninguna se acerca al límite de 15 minutos de Lambda por el OCR). Después junta las `claves` y los `fallos` de todas en un único evento.
- `Extraccion` invoca la etapa 3 con ese evento.

Cada tarea reintenta los errores transitorios del servicio Lambda; un `ErrorEtapa` o cualquier otro error del código hace fallar la ejecución. Para lanzarla a mano: consola de Step Functions → *Start execution* con, por ejemplo, `{"fecha": "20261119", "prefijo": "bestinver"}`.

Los fallos de documentos sueltos no hacen fallar la invocación (el detalle queda en el resumen y en CloudWatch Logs). Un error que impide ejecutar la etapa sí la hace fallar: `ErrorEtapa` (bucket inaccesible, no hay carpeta de fecha o nada que procesar) o `ValueError` (fecha o modo de OCR no válidos). Por consola, esos mismos errores se muestran y el script termina con código 1.

## Infraestructura (Terraform)

Toda la infraestructura de AWS (región `eu-west-3`) se define con Terraform en [`terraform/`](terraform/). El estado está en S3 (`s3://miax-adrian-pascua-wrkogph098767812/pipeline-fondos/terraform.tfstate`, con bloqueo por fichero `.tflock`).

| Fichero | Recursos |
|---|---|
| `etapas.tf` | Lista de etapas: carpeta, repositorio ECR, función Lambda, memoria, timeout y carpetas del bucket que lee y escribe. |
| `s3.tf` | Bucket `curso-miax-pipeline-fondos` (con `prevent_destroy`) y su bloqueo de acceso público. |
| `ecr.tf` | Un repositorio ECR por etapa, con política de ciclo de vida (se conservan las 10 últimas imágenes). |
| `lambda.tf` | Las tres funciones Lambda de tipo imagen y sus grupos de logs (retención de 30 días). |
| `iam.tf` | Un rol por Lambda con permisos mínimos: `s3:ListBucket` en el bucket, lectura de la carpeta de la etapa anterior, lectura/escritura de la suya y, en la etapa 3, `bedrock:InvokeModel`. |
| `step_functions.tf` | Máquina de estados `pipeline-fondos` y su rol. |
| `scheduler.tf` | Schedule mensual que lanza la máquina de estados, y su rol. |
| `despliegue.tf` | Política `pipeline-fondos-despliegue`, asociada al rol `miax-github-deploy` de GitHub Actions, con los permisos para aplicar este Terraform. |
| `variables.tf`, `outputs.tf` | Variables (región, bucket, programación, paralelismo de la etapa 2, retención de logs...) y salidas. |

El bucket, los repositorios ECR, las Lambdas, sus grupos de logs y el schedule ya existían: se incorporan al estado con bloques `import` la primera vez que se aplica. El proveedor OIDC de GitHub y el rol `miax-github-deploy` se crean fuera de este proyecto (los usan otros repositorios); Terraform solo le asocia la política de despliegue.

Memoria y timeout de cada Lambda: descarga 256 MB y 5 min; Markdown 3008 MB y 15 min (por invocación se convierte un PDF); extracción 512 MB y 15 min.

### Etiquetas de imagen

Cada imagen se etiqueta con el **SHA del último commit que cambió la carpeta de la etapa o `common/`**. Lo calcula [`terraform/etiquetas_imagen.sh`](terraform/etiquetas_imagen.sh), que genera la variable `etiquetas_imagen` en `terraform/imagenes.auto.tfvars.json` (no se versiona). Así, si solo cambia `pdf_markdown/`, solo cambia la etiqueta de esa etapa y Terraform solo actualiza esa Lambda; un cambio en `common/` cambia las tres. Solo cuenta lo que está commiteado.

### Uso en local

Desde Git Bash, con credenciales de AWS con permisos de administrador:

```bash
bash terraform/etiquetas_imagen.sh > terraform/imagenes.auto.tfvars.json
cd terraform
terraform init
terraform plan
terraform apply
```

**La primera vez hay que aplicarlo en local**, antes del primer push con el nuevo workflow: importa los recursos existentes y da al rol `miax-github-deploy` los permisos que necesita el workflow (sin ellos no puede leer el estado ni gestionar IAM). Los roles creados a mano antes de Terraform (`pipeline-fondos-*-role-*` en `service-role/` y `Amazon_EventBridge_Scheduler_LAMBDA_8f53be9dfd`) dejan de usarse y se pueden borrar desde la consola de IAM.

Si se aplica en local con una etiqueta cuya imagen aún no está en ECR, la actualización de la Lambda falla: en ese caso hay que hacer push y dejar que el workflow construya la imagen.

### Despliegue (GitHub Actions)

El workflow [`.github/workflows/deploy.yaml`](.github/workflows/deploy.yaml) se ejecuta en cada push a `main` (o a mano con *Run workflow*) y no permite dos ejecuciones a la vez. Se autentica en AWS por OIDC con el rol `miax-github-deploy` y tiene tres jobs:

1. **Preparar** (`preparar`): genera las etiquetas de imagen, aplica solo los repositorios de ECR (`terraform apply -target=aws_ecr_repository.etapa`, para que existan antes de subir imágenes) y comprueba qué etapas no tienen todavía en ECR la imagen con su etiqueta.
2. **Construir** (`construir`): con una matriz con esas etapas, construye cada imagen (desde la raíz del repo, para poder copiar `common/`) y la sube a ECR. Si todas las imágenes ya existen, no se ejecuta.
3. **Terraform apply** (`aplicar`): `terraform plan` y `apply` de toda la infraestructura. Solo se ejecuta si no ha fallado ninguna imagen.

Por tanto, un cambio en `terraform/` se aplica sin reconstruir imágenes; un cambio en la carpeta de una etapa reconstruye y despliega solo esa etapa; uno en `common/`, todas; y un cambio en otros ficheros (README, `CLAUDE.md`...) termina con un plan sin cambios.

Para añadir una etapa: su carpeta con `Dockerfile`, una entrada en `local.etapas` (`terraform/etapas.tf`) con la misma clave que la carpeta y, si se encadena, su estado en `terraform/step_functions.tf`.

## Próximas etapas

- [x] Extraer información de los KID descargados (PDF → Markdown → datos estructurados).
- [x] Leer los PDF de S3 y guardar los Markdown y los datos extraídos en S3.
- [ ] Añadir otras gestoras.
