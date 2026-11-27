# Programación del pipeline completo con EventBridge Scheduler. El schedule ya existía (apuntando
# a la Lambda de la etapa 1): se importa y ahora lanza la máquina de estados.
import {
  to = aws_scheduler_schedule.pipeline
  id = "default/descarga-bestinver-fondos"
}

resource "aws_scheduler_schedule" "pipeline" {
  name                         = "descarga-bestinver-fondos"
  group_name                   = "default"
  description                  = "Lanza el pipeline de fondos (descarga, Markdown y extraccion) una vez al mes"
  schedule_expression          = var.programacion
  schedule_expression_timezone = var.zona_horaria
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sfn_state_machine.pipeline.arn
    role_arn = aws_iam_role.scheduler.arn

    # Scheduler sustituye <aws.scheduler.scheduled-time> por la hora programada; la etapa 1
    # toma de ahí la carpeta de fecha, así un reintento escribe en la misma carpeta.
    input = jsonencode({
      time    = "<aws.scheduler.scheduled-time>"
      prefijo = var.gestora
    })

    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 3
    }
  }
}

data "aws_iam_policy_document" "asumir_scheduler" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.cuenta]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "pipeline-fondos-scheduler"
  assume_role_policy = data.aws_iam_policy_document.asumir_scheduler.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    sid       = "LanzarPipeline"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.pipeline.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "lanzar-pipeline"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}
