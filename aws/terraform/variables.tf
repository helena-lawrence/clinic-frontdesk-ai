variable "image_tag" {
  description = "Commit SHA published to Terraform-managed ECR repositories."
  type        = string
  default     = ""
}

variable "enable_services" {
  description = "Start ECS services after both images have been published."
  type        = bool
  default     = false
}

variable "cognito_domain_prefix" {
  description = "Globally unique Cognito prefix in eu-west-2."
  type        = string
  default     = "clinic-frontdesk-managed-202506667107"
}
