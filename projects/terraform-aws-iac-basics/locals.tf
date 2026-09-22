locals {
  public_subnets = {
    a = { cidr = "10.0.1.0/24", az = "ap-northeast-1a" }
    c = { cidr = "10.0.2.0/24", az = "ap-northeast-1c" }
  }

  private_subnets = {
    a = { cidr = "10.0.11.0/24", az = "ap-northeast-1a" }
    c = { cidr = "10.0.12.0/24", az = "ap-northeast-1c" }
  }

  common_tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}
