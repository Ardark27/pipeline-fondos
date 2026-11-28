# Bucket de datos del pipeline.
resource "aws_s3_bucket" "datos" {
  bucket = var.bucket

  # Guarda el histórico de documentos descargados: Terraform no debe borrarlo nunca
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "datos" {
  bucket = aws_s3_bucket.datos.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
