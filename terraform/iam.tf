# Rol de ejecución de cada Lambda, con los permisos mínimos sobre el bucket.

data "aws_iam_policy_document" "asumir_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  for_each = local.etapas

  name               = "${each.value.funcion}-lambda"
  assume_role_policy = data.aws_iam_policy_document.asumir_lambda.json
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  for_each = local.etapas

  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda" {
  for_each = local.etapas

  # head_bucket y listado de carpetas. ListBucket también hace que head_object devuelva 404 (y no 403)
  statement {
    sid       = "ListarBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.datos.arn]
  }

  dynamic "statement" {
    for_each = length(each.value.lee) > 0 ? [1] : []
    content {
      sid       = "LeerEtapaAnterior"
      actions   = ["s3:GetObject"]
      resources = [for carpeta in each.value.lee : "${aws_s3_bucket.datos.arn}/${carpeta}/*"]
    }
  }

  statement {
    sid       = "EscribirEtapa"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.datos.arn}/${each.value.escribe}/*"]
  }

  dynamic "statement" {
    for_each = each.value.usa_llm ? [1] : []
    content {
      sid     = "InvocarModeloBedrock"
      actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      # Perfil de inferencia global (global.<modelo>) y modelos base de las regiones a las que enruta
      resources = [
        "arn:aws:bedrock:*::foundation-model/*",
        "arn:aws:bedrock:*:${local.cuenta}:inference-profile/*",
      ]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  for_each = local.etapas

  name   = "acceso-pipeline"
  role   = aws_iam_role.lambda[each.key].id
  policy = data.aws_iam_policy_document.lambda[each.key].json
}
