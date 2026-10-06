terraform {
  required_version = ">= 1.9"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }

  # Partial configuration on purpose: the state path is passed at init time so the state
  # always lives outside the repository (see README.md), never next to the code.
  backend "local" {}
}

# Authentication comes from ~/.oci/config. No key material ever sits in this directory.
provider "oci" {
  auth                = "APIKey"
  config_file_profile = var.oci_profile
  region              = var.region
}
