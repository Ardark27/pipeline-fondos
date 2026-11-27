# Máquina de estados que encadena las tres etapas. Cada etapa recibe como entrada el resumen
# de la anterior (bucket, prefijo, fecha, claves...).
#
#   Descarga ──> Markdown (Map: un PDF por invocación, en paralelo) ──> Extraccion
#
# La etapa 2 se reparte en una invocación por PDF para no chocar con el límite de 15 minutos
# de Lambda (el OCR tarda varios segundos por página); después se juntan las claves de todos
# los Markdown en un único evento para la etapa 3.

locals {
  # Reintentos ante errores transitorios del servicio Lambda (no ante ErrorEtapa ni fallos del código)
  reintentos_lambda = [{
    ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException", "Lambda.TooManyRequestsException"]
    IntervalSeconds = 5
    MaxAttempts     = 3
    BackoffRate     = 2
  }]

  definicion_pipeline = {
    Comment       = "Pipeline de fondos: descarga -> Markdown -> extraccion de los KID"
    QueryLanguage = "JSONata"
    StartAt       = "Descarga"
    States = {
      Descarga = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Arguments = {
          FunctionName = aws_lambda_function.etapa["webscrapper"].arn
          Payload      = "{% $states.input %}"
        }
        Output = "{% $states.result.Payload %}"
        Retry  = local.reintentos_lambda
        Next   = "Markdown"
      }

      Markdown = {
        Type           = "Map"
        Items          = "{% $states.input.claves %}"
        MaxConcurrency = var.pdfs_en_paralelo
        ItemSelector = {
          bucket  = "{% $states.input.bucket %}"
          prefijo = "{% $states.input.prefijo %}"
          fecha   = "{% $states.input.fecha %}"
          claves  = "{% [$states.context.Map.Item.Value] %}"
        }
        ItemProcessor = {
          ProcessorConfig = { Mode = "INLINE" }
          StartAt         = "ConvertirPdf"
          States = {
            ConvertirPdf = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Arguments = {
                FunctionName = aws_lambda_function.etapa["pdf_markdown"].arn
                Payload      = "{% $states.input %}"
              }
              Output = "{% $states.result.Payload %}"
              Retry  = local.reintentos_lambda
              End    = true
            }
          }
        }
        # Junta los resúmenes de cada PDF en un único evento para la etapa 3
        Output = "{% {'bucket': $states.input.bucket, 'prefijo': $states.input.prefijo, 'fecha': $states.input.fecha, 'claves': [$states.result.claves], 'fallos': [$states.result.fallos]} %}"
        Next   = "Extraccion"
      }

      Extraccion = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Arguments = {
          FunctionName = aws_lambda_function.etapa["structured_output"].arn
          Payload      = "{% $states.input %}"
        }
        Output = "{% $states.result.Payload %}"
        Retry  = local.reintentos_lambda
        End    = true
      }
    }
  }
}

resource "aws_sfn_state_machine" "pipeline" {
  name       = "pipeline-fondos"
  role_arn   = aws_iam_role.step_functions.arn
  definition = jsonencode(local.definicion_pipeline)
}

data "aws_iam_policy_document" "asumir_step_functions" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "step_functions" {
  name               = "pipeline-fondos-step-functions"
  assume_role_policy = data.aws_iam_policy_document.asumir_step_functions.json
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    sid     = "InvocarEtapas"
    actions = ["lambda:InvokeFunction"]
    resources = flatten([
      for funcion in aws_lambda_function.etapa : [funcion.arn, "${funcion.arn}:*"]
    ])
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "invocar-etapas"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}
