variable "image_tag" {
  description = "ECR image tag the service runs"
  type        = string
  default     = "develop"
}

variable "db_password" {
  description = "RDS master password (also stored at /open-label/staging/POSTGRE_PASSWORD)"
  type        = string
  sensitive   = true
}

variable "ls_username" {
  description = "Label Studio bootstrap admin username (email)"
  type        = string
}

variable "control_plane_base_url" {
  description = "OpenTrain control plane base URL (stable main Preview alias)"
  type        = string
}

variable "service_desired_count" {
  description = "ECS service desired task count"
  type        = number
  default     = 1
}
