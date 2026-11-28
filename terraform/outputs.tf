output "repositorios" {
  description = "URL del repositorio de ECR de cada etapa (lo usa el workflow para subir las imágenes)."
  value       = { for etapa, repo in aws_ecr_repository.etapa : etapa => repo.repository_url }
}

output "funciones" {
  description = "Nombre de la función Lambda de cada etapa."
  value       = { for etapa, funcion in aws_lambda_function.etapa : etapa => funcion.function_name }
}

output "imagenes" {
  description = "Imagen desplegada en cada Lambda."
  value       = { for etapa, funcion in aws_lambda_function.etapa : etapa => funcion.image_uri }
}

output "maquina_estados" {
  description = "ARN de la máquina de estados que encadena las etapas."
  value       = aws_sfn_state_machine.pipeline.arn
}
