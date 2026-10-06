data "oci_objectstorage_namespace" "this" {
  compartment_id = var.tenancy_ocid
}

# Qdrant snapshots and MLflow archives land here (daily CronJob, J13). Standard tier stays
# inside the 20 GB Always Free allowance; Archive tier would bill restores.
resource "oci_objectstorage_bucket" "backups" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = "vigie-backups"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Disabled"
  freeform_tags  = local.tags
}

locals {
  # Policy statements address the root compartment as "tenancy", not by its OCID.
  policy_scope = var.compartment_ocid == var.tenancy_ocid ? "tenancy" : "compartment id ${var.compartment_ocid}"
}

# Object Storage needs this grant before it may delete objects on our behalf, otherwise the
# lifecycle policy below is rejected.
resource "oci_identity_policy" "objectstorage_lifecycle" {
  compartment_id = var.tenancy_ocid
  name           = "vigie-objectstorage-lifecycle"
  description    = "Autorise Object Storage à purger les sauvegardes Vigie arrivées à échéance."
  statements = [
    "Allow service objectstorage-${var.region} to manage object-family in ${local.policy_scope}",
  ]
  freeform_tags = local.tags
}

# Backups may contain audit journal extracts, which must not outlive the 30 day retention.
resource "oci_objectstorage_object_lifecycle_policy" "backups" {
  namespace = data.oci_objectstorage_namespace.this.namespace
  bucket    = oci_objectstorage_bucket.backups.name

  rules {
    name        = "purge-after-retention"
    action      = "DELETE"
    is_enabled  = true
    target      = "objects"
    time_amount = var.backup_retention_days
    time_unit   = "DAYS"
  }

  depends_on = [oci_identity_policy.objectstorage_lifecycle]
}
