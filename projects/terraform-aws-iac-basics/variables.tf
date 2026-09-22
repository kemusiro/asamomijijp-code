variable "project_name" {
  description = "リソース名に付ける接頭辞"
  type        = string
  default     = "tf-web-demo"

  validation {
    condition     = length(var.project_name) <= 20 && can(regex("^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", var.project_name))
    error_message = "project_nameは20文字以下の英小文字、数字、ハイフンで指定し、先頭と末尾にはハイフンを使用しないでください。"
  }
}

variable "ami_id" {
  description = "東京リージョンで利用できるAmazon Linux 2023 x86_64 AMIのID"
  type        = string

  validation {
    condition     = can(regex("^ami-[0-9a-f]+$", var.ami_id))
    error_message = "ami_idにはami-で始まるAMI IDを指定してください。"
  }
}

variable "allowed_ingress_cidr" {
  description = "ALBのHTTPアクセスを許可する確認端末の公開IPv4 CIDR"
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_ingress_cidr, 0)) && !strcontains(var.allowed_ingress_cidr, ":")
    error_message = "allowed_ingress_cidrには有効なIPv4 CIDRを指定してください。"
  }
}

variable "instance_type" {
  description = "EC2インスタンスタイプ"
  type        = string
  default     = "t3.micro"
}
