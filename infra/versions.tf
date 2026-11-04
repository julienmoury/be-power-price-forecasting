terraform {
  required_version = "= 1.16.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.69.1"
    }
  }

  # State in the bucket and lock table of infra/bootstrap/bootstrap.yaml, given at init:
  #   terraform init -backend-config=bucket=... -backend-config=dynamodb_table=...
  backend "s3" {
    key     = "be-power-forecast/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "be-power-forecast"
      ManagedBy = "terraform"
    }
  }
}
