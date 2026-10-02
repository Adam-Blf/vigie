resource "oci_core_vcn" "vigie" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.10.0.0/16"]
  display_name   = "vigie-vcn"
  dns_label      = "vigie"
  freeform_tags  = local.tags
}

resource "oci_core_internet_gateway" "vigie" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vigie.id
  display_name   = "vigie-igw"
  enabled        = true
  freeform_tags  = local.tags
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vigie.id
  display_name   = "vigie-public-rt"
  freeform_tags  = local.tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.vigie.id
  }
}

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.vigie.id
  display_name   = "vigie-public-sl"
  freeform_tags  = local.tags

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH is the only administrative door and it only opens to the admin IP. The Kubernetes
  # API (6443) is deliberately absent: it is reached through an SSH tunnel.
  ingress_security_rules {
    source   = var.admin_cidr
    protocol = local.proto_tcp
    tcp_options {
      min = 22
      max = 22
    }
  }

  dynamic "ingress_security_rules" {
    for_each = toset([80, 443])
    content {
      source   = "0.0.0.0/0"
      protocol = local.proto_tcp
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  # Without "fragmentation needed" messages, path MTU discovery breaks and large TLS
  # responses stall silently, which is miserable to debug.
  ingress_security_rules {
    source   = "0.0.0.0/0"
    protocol = local.proto_icmp
    icmp_options {
      type = 3
      code = 4
    }
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.vigie.id
  cidr_block                 = "10.10.1.0/24"
  display_name               = "vigie-public"
  dns_label                  = "public"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = local.tags
}
