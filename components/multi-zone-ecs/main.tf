variable "name" {
  description = "Resource name prefix"
  type        = string
  default     = "tf_example"
}

variable "vpc_cidr_block" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.4.0.0/16"
}

variable "zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = []
}

variable "vswitch_cidrs" {
  description = "List of CIDR blocks for vSwitches"
  type        = list(string)
}

variable "instance_name" {
  description = "ECS instance name prefix"
  type        = string
}

variable "instance_type" {
  description = "ECS instance type"
  type        = string
}

variable "image_id" {
  description = "ECS instance image ID"
  type        = string
}

variable "ingress_rules" {
  description = "Security group ingress rules"
  type = map(object({
    ip_protocol   = string
    port_range    = string
    source_cidr   = optional(string, "0.0.0.0/0")
    priority      = optional(string, "1")
    description   = optional(string, "")
    ipv6_src_cidr = optional(string, "")
    nic_type      = optional(string, "intranet")
    policy        = optional(string, "accept")
  }))
  default = {}
}

variable "egress_rules" {
  description = "Security group egress rules"
  type = map(object({
    ip_protocol    = string
    port_range     = string
    dest_cidr      = optional(string, "0.0.0.0/0")
    priority       = optional(string, "1")
    description    = optional(string, "")
    ipv6_dest_cidr = optional(string, "")
    nic_type       = optional(string, "intranet")
    policy         = optional(string, "accept")
  }))
  default = {}
}


# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name            = var.name
  cidr_block      = var.vpc_cidr_block
  zones           = var.zones
  vswitch_cidrs   = var.vswitch_cidrs
}

# Security Group Module
module "security_group" {
  source = "../../modules/security-group"

  name          = var.name
  vpc_id        = module.vpc.vpc_id
  ingress_rules = var.ingress_rules
  egress_rules  = var.egress_rules
}

# ECS Instances - One instance per zone
module "ecs_instances" {
  source = "../../modules/ecs-instance"
  for_each = { for i, vswitch_cidr in var.vswitch_cidrs : vswitch_cidr => i }

  instance_name     = "${var.instance_name}-${each.key}"
  instance_type     = var.instance_type
  availability_zone = module.vpc.zones[each.key]
  image_id          = var.image_id
  security_groups   = [module.security_group.security_group_id]
  vswitch_id        = module.vpc.vswitch_ids[each.key]
}

output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vswitch_ids" {
  description = "The IDs of the vSwitches"
  value       = module.vpc.vswitch_ids
}

output "security_group_id" {
  description = "The ID of the security group"
  value       = module.security_group.security_group_id
}

output "ecs_instance_ids" {
  description = "Map of ECS instance IDs"
  value       = { for k, v in module.ecs_instances : k => v.id }
}

output "ecs_private_ips" {
  description = "Map of ECS instance private IPs"
  value       = { for k, v in module.ecs_instances : k => v.private_ip }
}
