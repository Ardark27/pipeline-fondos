terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # El estado vive en S3 (bucket creado fuera de este proyecto). use_lockfile bloquea el
  # estado con un objeto .tflock en el mismo bucket, sin necesidad de DynamoDB.
  backend "s3" {
    bucket       = "miax-adrian-pascua-wrkogph098767812"
    key          = "pipeline-fondos/terraform.tfstate"
    region       = "eu-west-3"
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Proyecto      = "pipeline-fondos"
      GestionadoPor = "terraform"
    }
  }
}

data "aws_caller_identity" "actual" {}
