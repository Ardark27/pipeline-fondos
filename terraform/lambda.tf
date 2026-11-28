# Funciones Lambda de cada etapa (imagen Docker).
resource "aws_lambda_function" "etapa" {
  for_each = local.etapas

  function_name = each.value.funcion
  description   = each.value.descripcion
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.etapa[each.key].repository_url}:${var.etiquetas_imagen[each.key]}"
  architectures = ["x86_64"]
  role          = aws_iam_role.lambda[each.key].arn
  memory_size   = each.value.memoria
  timeout       = each.value.timeout

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.etapa[each.key].name
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_iam_role_policy.lambda,
  ]
}

# Grupos de logs de las Lambdas, con retención fija
resource "aws_cloudwatch_log_group" "etapa" {
  for_each = local.etapas

  name              = "/aws/lambda/${each.value.funcion}"
  retention_in_days = var.dias_retencion_logs
}
