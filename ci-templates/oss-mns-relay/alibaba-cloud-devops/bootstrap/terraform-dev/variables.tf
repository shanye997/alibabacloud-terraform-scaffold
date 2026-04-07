# Variables for IaC Service Bootstrap
# Only user-configurable settings are defined here

variable "bucket_name" {
  description = "The name of the OSS bucket for code storage. If empty, a random name will be generated"
  type        = string
  default     = null
}


variable "ram_role_name" {
  description = "The name of the RAM role for the Iac Terraform Stack. The default value is 'IaCServiceStackRole'"
  type        = string
  default     = "IaCServiceStackRoleTest"
}