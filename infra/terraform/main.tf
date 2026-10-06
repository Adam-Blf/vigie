locals {
  # Free-form tags rather than defined tags: they need no tag namespace, so no extra IAM
  # setup, and they still let the console filter everything that belongs to the course.
  tags = {
    Project = "vigie"
    Course  = "MLOps"
  }

  # OCI security lists want IANA protocol numbers as strings.
  proto_tcp  = "6"
  proto_icmp = "1"
}

data "oci_identity_availability_domains" "all" {
  compartment_id = var.tenancy_ocid
}

# Latest Ubuntu 24.04 build for Ampere. The regex keeps the full image and drops the
# "Minimal" variant, which lacks tools cloud-init relies on.
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = ["^Canonical-Ubuntu-24\\.04-aarch64-.*"]
    regex  = true
  }
}

resource "oci_core_instance" "vigie" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.all.availability_domains[var.ad_number - 1].name
  display_name        = "vigie-node"
  shape               = "VM.Standard.A1.Flex"
  freeform_tags       = local.tags

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_arm.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.public.id
    assign_public_ip = true
    display_name     = "vigie-node-vnic"
    hostname_label   = "vigie-node"
    freeform_tags    = local.tags
  }

  # IMDSv1 answers any plain GET, so a single SSRF in a pod could read instance metadata.
  # v2 requires the "Authorization: Bearer Oracle" header that such a bug cannot add.
  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    # Only public, versioned settings go in here: user_data is readable by anything on
    # the VM that can reach the metadata service.
    user_data = base64encode(templatefile("${path.module}/cloud-init.sh", {
      k3s_version = var.k3s_version
    }))
  }

  preserve_boot_volume = false

  lifecycle {
    # A newer Ubuntu image or an edited bootstrap script must not destroy a running node
    # on the next apply. Rebuilding is an explicit decision (terraform apply -replace).
    ignore_changes = [
      source_details[0].source_id,
      metadata["user_data"],
    ]
  }
}
