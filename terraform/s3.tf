# Bucket de datos del pipeline. Ya existía: se importa en lugar de crearse.
import {
  to = aws_s3_bucket.datos
  id = var.bucket
}

resource "aws_s3_bucket" "datos" {
  bucket = var.bucket

  # Guarda el histórico de documentos descargados: Terraform no debe borrarlo nunca
  lifecycle {
    prevent_destroy = true
  }
}

import {
  to = aws_s3_bucket_public_access_block.datos
  id = var.bucket
}

resource "aws_s3_bucket_public_access_block" "datos" {
  bucket = aws_s3_bucket.datos.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
