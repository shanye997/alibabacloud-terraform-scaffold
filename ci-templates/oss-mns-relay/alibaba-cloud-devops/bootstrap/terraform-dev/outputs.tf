# Outputs for IaC Service Bootstrap
# Essential outputs for integration with other systems

# RAM Role Outputs
output "ram_role_arn" {
  description = "The ARN of the created RAM role for IaC service"
  value       = alicloud_ram_role.iac_service_role.arn
}

output "ram_role_name" {
  description = "The name of the created RAM role"
  value       = alicloud_ram_role.iac_service_role.role_name
}

# OSS Bucket Outputs
output "oss_bucket" {
  description = "The name of the created OSS bucket for code storage"
  value       = alicloud_oss_bucket.code_storage.id
}


output "oss_region" {
  description = "The region of the created OSS bucket"
  value       = "cn-beijing"
}
