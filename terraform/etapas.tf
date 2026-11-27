# Etapas del pipeline. La clave es la carpeta del repo que contiene el Dockerfile de la etapa.
# Una etapa nueva se añade aquí y, si debe encadenarse, en step_functions.tf.
locals {
  etapas = {
    webscrapper = {
      repositorio = "webscrapper-miax-14"
      funcion     = "pipeline-fondos-descarga"
      descripcion = "Etapa 1: descarga los PDF de los fondos de Bestinver a download/"
      memoria     = 256
      timeout     = 300
      # Permisos sobre el bucket: carpetas que lee y carpeta en la que escribe
      lee     = []
      escribe = "download"
      usa_llm = false
    }
    pdf_markdown = {
      repositorio = "pdf-to-markdown-miax-14"
      funcion     = "pipeline-fondos-markdown"
      descripcion = "Etapa 2: convierte los PDF de download/ a Markdown en markdown/ (con OCR)"
      memoria     = 3008
      timeout     = 900
      lee         = ["download"]
      escribe     = "markdown"
      usa_llm     = false
    }
    structured_output = {
      repositorio = "structured-output-miax-14"
      funcion     = "pipeline-fondos-extraccion"
      descripcion = "Etapa 3: extrae con un LLM de Bedrock los datos de los KID de markdown/ a extraction/"
      memoria     = 512
      timeout     = 900
      lee         = ["markdown"]
      escribe     = "extraction"
      usa_llm     = true
    }
  }

  cuenta = data.aws_caller_identity.actual.account_id
}
