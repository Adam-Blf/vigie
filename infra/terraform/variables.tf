variable "region" {
  description = "OCI region. Paris is the home region of the tenancy, Always Free compute only works there."
  type        = string
  default     = "eu-paris-1"
}

variable "oci_profile" {
  description = "Profile name in ~/.oci/config."
  type        = string
  default     = "DEFAULT"
}

variable "tenancy_ocid" {
  description = "Tenancy OCID. Budgets and IAM policies must be created at the tenancy root."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment that holds every Vigie resource."
  type        = string
}

variable "ad_number" {
  description = "Availability domain index, 1-based. eu-paris-1 only has one, so changing it is no fix for capacity errors there."
  type        = number
  default     = 1
}

variable "ocpus" {
  description = "Ampere A1 OCPUs. The Always Free allowance is 2 OCPUs since 2026, never go above."
  type        = number
  default     = 2

  validation {
    condition     = var.ocpus >= 1 && var.ocpus <= 2
    error_message = "Always Free allows at most 2 A1 OCPUs."
  }
}

variable "memory_gb" {
  description = "Ampere A1 memory in GB. The Always Free allowance is 12 GB since 2026."
  type        = number
  default     = 12

  validation {
    condition     = var.memory_gb >= 1 && var.memory_gb <= 12
    error_message = "Always Free allows at most 12 GB of A1 memory."
  }
}

variable "boot_volume_gb" {
  description = "Boot volume size. Always Free covers 200 GB of block storage in total."
  type        = number
  default     = 50

  validation {
    condition     = var.boot_volume_gb >= 50 && var.boot_volume_gb <= 200
    error_message = "Boot volume must stay between 50 GB (OCI minimum) and 200 GB (Always Free total)."
  }
}

variable "admin_cidr" {
  description = "Only source allowed on SSH, as a /32 of the administrator public IP."
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must be a valid CIDR and never the whole Internet."
  }
}

variable "ssh_public_key" {
  description = "Public half of ~/.ssh/vigie_deploy."
  type        = string
}

variable "budget_email" {
  description = "Recipient of the budget alert."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in the account currency. Anything above zero spend is a mistake, so it stays tiny."
  type        = number
  default     = 1
}

variable "budget_alert_percent" {
  description = "Alert threshold, in percent of the budget, on actual spend."
  type        = number
  default     = 1
}

variable "k3s_version" {
  description = "Pinned k3s release, so a rebuilt VM gets exactly the same control plane."
  type        = string
  default     = "v1.36.5+k3s1"
}

variable "backup_retention_days" {
  description = "Backups older than this are deleted by Object Storage, in line with the 30 day audit retention."
  type        = number
  default     = 30
}
