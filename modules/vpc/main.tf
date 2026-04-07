variable "name" {
  description = "VPC name"
  type        = string
  default     = "tf_example"
}

variable "cidr_block" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.4.0.0/16"
}

variable "zones" {
  description = "List of zones for vSwitches"
  type        = list(string)
}

variable "vswitch_cidrs" {
  description = "List of CIDR blocks for vSwitches (must match zones length)"
  type        = list(string)
}

resource "alicloud_vpc" "default" {
  vpc_name   = var.name
  cidr_block = var.cidr_block
}

resource "alicloud_vswitch" "default" {
  for_each     = { for i, vswitch_cidr in var.vswitch_cidrs : vswitch_cidr => i }
  vpc_id       = alicloud_vpc.default.id
  cidr_block   = each.key
  zone_id      = var.zones[each.value % length(var.zones)]
  vswitch_name = format("${var.name}_%d", each.value + 1)
}

output "vpc_id" {
  description = "The ID of the VPC"
  value       = alicloud_vpc.default.id
}

output "vswitch_ids" {
  description = "The IDs of the vSwitches"
  value       = { for i, vswitch in alicloud_vswitch.default : i => vswitch.id }
}

output "zones" {
  description = "The list of availability zones"
  value       = { for i, vswitch in alicloud_vswitch.default : i => vswitch.zone_id }
}
