variable "name" {
  description = "Security group name"
  type        = string
}

variable "vpc_id" {
  description = "The ID of the VPC"
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
    nic_type       = optional(string, "intranet")
    policy         = optional(string, "accept")
  }))
  default = {}
}

resource "alicloud_security_group" "default" {
  security_group_name = var.name
  description         = var.name
  vpc_id              = var.vpc_id
}

resource "alicloud_security_group_rule" "ingress" {
  for_each = var.ingress_rules

  type              = "ingress"
  ip_protocol       = each.value.ip_protocol
  port_range        = each.value.port_range
  security_group_id = alicloud_security_group.default.id
  cidr_ip           = each.value.source_cidr
  priority          = each.value.priority
  description       = each.value.description
  nic_type          = each.value.nic_type
  policy            = each.value.policy
}

resource "alicloud_security_group_rule" "egress" {
  for_each = var.egress_rules

  type              = "egress"
  ip_protocol       = each.value.ip_protocol
  port_range        = each.value.port_range
  security_group_id = alicloud_security_group.default.id
  cidr_ip           = each.value.dest_cidr
  priority          = each.value.priority
  description       = each.value.description
  nic_type          = each.value.nic_type
  policy            = each.value.policy
}

output "security_group_id" {
  description = "The ID of the security group"
  value       = alicloud_security_group.default.id
}

output "ingress_rule_ids" {
  description = "The IDs of the ingress rules"
  value       = [for k, v in alicloud_security_group_rule.ingress : v.id]
}

output "egress_rule_ids" {
  description = "The IDs of the egress rules"
  value       = [for k, v in alicloud_security_group_rule.egress : v.id]
}
