# Un repositorio de ECR por etapa. Ya existían: se importan.
import {
  for_each = local.etapas
  to       = aws_ecr_repository.etapa[each.key]
  id       = each.value.repositorio
}

resource "aws_ecr_repository" "etapa" {
  for_each = local.etapas

  name                 = each.value.repositorio
  image_tag_mutability = "MUTABLE"
}

# Solo se conservan las últimas imágenes de cada repositorio
resource "aws_ecr_lifecycle_policy" "etapa" {
  for_each = local.etapas

  repository = aws_ecr_repository.etapa[each.key].name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar las 10 imagenes mas recientes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
