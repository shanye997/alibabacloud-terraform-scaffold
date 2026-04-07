variable "instance_name" {
  description = "The name of the ECS instance"
  type        = string
}

variable "instance_type" {
  description = "The instance type of the ECS instance"
  type        = string
}

variable "availability_zone" {
  description = "The availability zone of the ECS instance"
  type        = string
}

variable "image_id" {
  description = "The image ID of the ECS instance"
  type        = string
}

variable "security_groups" {
  description = "The security groups of the ECS instance"
  type        = list(string)
}

variable "vswitch_id" {
  description = "The vSwitch ID of the ECS instance"
  type        = string
}

resource "alicloud_instance" "default" {
  instance_name     = var.instance_name
  instance_type     = var.instance_type
  availability_zone = var.availability_zone
  image_id          = var.image_id
  security_groups   = var.security_groups
  vswitch_id        = var.vswitch_id
}

output "id" {
  description = "The ID of the ECS instance"
  value       = alicloud_instance.default.id
}

output "private_ip" {
  description = "The private IP of the ECS instance"
  value       = alicloud_instance.default.private_ip
}
