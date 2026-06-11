terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "opentrain-tfstate-362353308385"
    key          = "open-label/staging/terraform.tfstate"
    region       = "us-east-1"
    profile      = "opentrain-admin"
    use_lockfile = true
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "opentrain-admin"

  default_tags {
    tags = {
      project    = "open-label"
      env        = "staging"
      managed_by = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name        = "open-label-staging"
  account_id  = data.aws_caller_identity.current.account_id
  region      = "us-east-1"
  domain      = "annotate.opentrain.work"
  zone_id     = "Z01008602FOF2OTD2LN7R"
  ssm_prefix  = "/open-label/staging"
  media_bucket = "open-label-staging-media-${data.aws_caller_identity.current.account_id}"
}
