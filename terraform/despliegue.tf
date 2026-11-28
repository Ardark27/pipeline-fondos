# Permisos que necesita GitHub Actions para aplicar este Terraform.
#
# El proveedor OIDC de GitHub y el rol miax-github-deploy se crearon fuera de este proyecto
# (los comparten otros repositorios), así que aquí solo se le añade una política con lo
# necesario para gestionar los recursos del pipeline. La primera vez se aplica en local con
# credenciales de administrador; a partir de ahí, el workflow ya tiene estos permisos.

data "aws_iam_role" "despliegue" {
  name = var.rol_despliegue
}

data "aws_iam_policy_document" "despliegue" {
  statement {
    sid       = "EstadoTerraformListar"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.bucket_estado}"]
  }

  statement {
    sid     = "EstadoTerraform"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "arn:aws:s3:::${var.bucket_estado}/pipeline-fondos/terraform.tfstate",
      "arn:aws:s3:::${var.bucket_estado}/pipeline-fondos/terraform.tfstate.tflock",
    ]
  }

  # Configuración del bucket de datos (no sus objetos)
  statement {
    sid       = "BucketDatos"
    actions   = ["s3:Get*", "s3:List*", "s3:PutBucket*", "s3:PutEncryptionConfiguration", "s3:PutLifecycleConfiguration"]
    resources = [aws_s3_bucket.datos.arn]
  }

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken", "ecr:DescribeRepositories"]
    resources = ["*"]
  }

  # Todos los repositorios de la cuenta: una etapa nueva crea su repositorio antes de que esta
  # política se actualice con su nombre
  statement {
    sid       = "EcrRepositorios"
    actions   = ["ecr:*"]
    resources = ["arn:aws:ecr:${var.region}:${local.cuenta}:repository/*"]
  }

  statement {
    sid       = "Lambdas"
    actions   = ["lambda:*"]
    resources = ["arn:aws:lambda:${var.region}:${local.cuenta}:function:pipeline-fondos-*"]
  }

  statement {
    sid       = "LogsListar"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid     = "Logs"
    actions = ["logs:*"]
    resources = [
      "arn:aws:logs:${var.region}:${local.cuenta}:log-group:/aws/lambda/pipeline-fondos-*",
      "arn:aws:logs:${var.region}:${local.cuenta}:log-group:/aws/lambda/pipeline-fondos-*:*",
    ]
  }

  statement {
    sid       = "StepFunctions"
    actions   = ["states:*"]
    resources = ["arn:aws:states:${var.region}:${local.cuenta}:stateMachine:pipeline-fondos*"]
  }

  statement {
    sid       = "Scheduler"
    actions   = ["scheduler:*"]
    resources = ["arn:aws:scheduler:${var.region}:${local.cuenta}:schedule/default/descarga-bestinver-fondos"]
  }

  # Roles y políticas del pipeline (todos empiezan por pipeline-fondos-)
  statement {
    sid     = "IamPipeline"
    actions = ["iam:*"]
    resources = [
      "arn:aws:iam::${local.cuenta}:role/pipeline-fondos-*",
      "arn:aws:iam::${local.cuenta}:policy/pipeline-fondos-*",
    ]
  }

  # Para leer el rol de despliegue y mantener esta misma política asociada
  statement {
    sid       = "IamRolDespliegue"
    actions   = ["iam:GetRole", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies", "iam:AttachRolePolicy"]
    resources = [data.aws_iam_role.despliegue.arn]
  }
}

resource "aws_iam_policy" "despliegue" {
  name        = "pipeline-fondos-despliegue"
  description = "Permisos de GitHub Actions para aplicar el Terraform de pipeline-fondos"
  policy      = data.aws_iam_policy_document.despliegue.json
}

resource "aws_iam_role_policy_attachment" "despliegue" {
  role       = data.aws_iam_role.despliegue.name
  policy_arn = aws_iam_policy.despliegue.arn
}
