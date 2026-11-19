# pipeline-fondos

Proyecto para extraer información de los KID (Documento de Datos Fundamentales) y fichas de fondos de inversión.

La primera etapa del pipeline descarga, mediante web scraping, los documentos de los fondos de **Bestinver** y los guarda en **Amazon S3**.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

Dependencias: `requests` (peticiones HTTP), `lxml` (parseo HTML y XPath) y `boto3[crt]` (subida a S3; el extra `crt` es necesario si las credenciales se obtienen con `aws login`).

### Credenciales de AWS

El script usa la cadena de credenciales estándar de AWS: `aws login` / `aws configure`, variables de entorno (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) o un perfil con `AWS_PROFILE`. La cuenta necesita permisos `s3:PutObject` y `s3:ListBucket` sobre el bucket `curso-miax-pipeline-fondos`.

## Etapa 1: descarga de documentos de Bestinver

Script: [`descargar_kids_bestinver.py`](descargar_kids_bestinver.py)

```bash
python descargar_kids_bestinver.py                       # sube a s3://curso-miax-pipeline-fondos/bestinver/<hoy>/
python descargar_kids_bestinver.py --fecha 20261119      # fuerza la carpeta de fecha (AAAAMMDD)
python descargar_kids_bestinver.py --bucket otro-bucket  # bucket distinto
python descargar_kids_bestinver.py --prefijo pruebas     # carpeta raíz distinta dentro del bucket
python descargar_kids_bestinver.py --delay 0.5           # segundos entre peticiones (por defecto 1.0)
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
- **37 PDFs** subidos a `s3://curso-miax-pipeline-fondos/bestinver/20261119/`: 22 "Datos fundamentales" y 15 "Fichas del fondo".
- Sin ficha publicada en la web: Latam, Solidario y Bonos Institucional I–V.
- `Otros` y `SICAV Luxemburguesas` son páginas que agrupan varios productos y no tienen estos documentos.

## Próximas etapas

- [ ] Extraer información de los KID descargados (PDF → datos estructurados).
- [ ] Añadir otras gestoras.
