variable "region" {
  description = "Región de AWS donde se despliega el pipeline."
  type        = string
  default     = "eu-west-3"
}

variable "bucket" {
  description = "Bucket de S3 donde leen y escriben todas las etapas (download/, markdown/, extraction/)."
  type        = string
  default     = "curso-miax-pipeline-fondos"
}

variable "etiquetas_imagen" {
  description = <<-EOT
    Etiqueta de la imagen de ECR que usa cada etapa (clave = carpeta de la etapa).
    La genera terraform/etiquetas_imagen.sh: es el SHA del último commit que cambió la carpeta
    de la etapa o common/, así que solo cambia (y solo se actualiza la Lambda) cuando cambia su código.
  EOT
  type        = map(string)

  validation {
    condition     = alltrue([for etapa in keys(local.etapas) : contains(keys(var.etiquetas_imagen), etapa)])
    error_message = "Falta la etiqueta de imagen de alguna etapa. Genéralas con: bash terraform/etiquetas_imagen.sh > terraform/imagenes.auto.tfvars.json"
  }
}

variable "programacion" {
  description = "Expresión de EventBridge Scheduler con la que se lanza el pipeline completo."
  type        = string
  default     = "cron(0 9 15 * ? *)" # día 15 de cada mes a las 9:00
}

variable "zona_horaria" {
  description = "Zona horaria de la programación."
  type        = string
  default     = "Europe/Madrid"
}

variable "gestora" {
  description = "Prefijo (gestora) con el que se lanza el pipeline programado."
  type        = string
  default     = "bestinver"
}

variable "pdfs_en_paralelo" {
  description = "Número máximo de PDF que la etapa 2 convierte a la vez (invocaciones simultáneas de su Lambda)."
  type        = number
  default     = 5
}

variable "dias_retencion_logs" {
  description = "Días que se conservan los logs de las Lambdas y de Step Functions en CloudWatch."
  type        = number
  default     = 30
}

variable "rol_despliegue" {
  description = "Rol de IAM (creado fuera de este proyecto) que asume GitHub Actions por OIDC para aplicar Terraform."
  type        = string
  default     = "miax-github-deploy"
}

variable "bucket_estado" {
  description = "Bucket donde se guarda el estado de Terraform (el mismo que el del backend)."
  type        = string
  default     = "miax-adrian-pascua-wrkogph098767812"
}
