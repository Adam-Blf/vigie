"""Static checks on the Terraform code.

terraform validate only proves the syntax. These tests pin the security and cost choices
that a careless edit could undo without any tool noticing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TF_DIR = Path(__file__).resolve().parents[1] / "infra" / "terraform"
CLOUD_INIT = (TF_DIR / "cloud-init.sh").read_text(encoding="utf-8")


def tf(name: str) -> str:
    return (TF_DIR / name).read_text(encoding="utf-8")


def all_tf() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(TF_DIR.glob("*.tf")))


def test_provider_is_pinned_and_uses_config_profile() -> None:
    versions = tf("versions.tf")
    assert 'source  = "oracle/oci"' in versions
    assert 'version = "~> 7.0"' in versions
    assert "config_file_profile = var.oci_profile" in versions
    assert "private_key" not in versions


def test_state_backend_is_left_to_init_time() -> None:
    # An empty local backend forces -backend-config, so the state never lands in the repo.
    assert 'backend "local" {}' in tf("versions.tf")


def test_legacy_metadata_endpoints_are_disabled() -> None:
    assert "are_legacy_imds_endpoints_disabled = true" in tf("main.tf")


def test_shape_stays_inside_always_free() -> None:
    variables = tf("variables.tf")
    assert "var.ocpus <= 2" in variables
    assert "var.memory_gb <= 12" in variables
    assert 'shape               = "VM.Standard.A1.Flex"' in tf("main.tf")


def test_every_taggable_resource_carries_project_tags() -> None:
    main = tf("main.tf")
    assert 'Project = "vigie"' in main
    assert 'Course  = "MLOps"' in main
    code = all_tf()
    resources = re.findall(r'resource "(\w+)" "\w+"', code)
    # The lifecycle policy is the only OCI resource without free-form tags.
    taggable = [r for r in resources if r != "oci_objectstorage_object_lifecycle_policy"]
    assert code.count("freeform_tags") >= len(taggable)


def test_ssh_only_opens_to_admin_and_kube_api_stays_closed() -> None:
    network = tf("network.tf")
    ssh_rule = network.split("min = 22")[0].rsplit("ingress_security_rules", 1)[1]
    assert "source   = var.admin_cidr" in ssh_rule
    assert not re.search(r"(min|max)\s*=\s*6443", network)
    assert "for_each = toset([80, 443])" in network


def test_budget_alerts_on_first_cent() -> None:
    budget = tf("budget.tf")
    assert 'type           = "ACTUAL"' in budget
    assert 'threshold_type = "PERCENTAGE"' in budget
    variables = tf("variables.tf")
    assert re.search(r'variable "budget_amount".*?default\s+= 1\n', variables, re.S)
    assert re.search(r'variable "budget_alert_percent".*?default\s+= 1\n', variables, re.S)


def test_backup_bucket_is_private_and_purged() -> None:
    storage = tf("storage.tf")
    assert 'access_type    = "NoPublicAccess"' in storage
    assert 'action      = "DELETE"' in storage


@pytest.mark.parametrize(
    "line",
    [
        "PasswordAuthentication no",
        "PermitRootLogin no",
        "netfilter-persistent save",
        "--write-kubeconfig-mode 600",
        "--secrets-encryption",
        "unattended-upgrades",
        "fail2ban",
        "--dports 80,443",
        "vigie-keepalive.timer",
    ],
)
def test_cloud_init_hardening(line: str) -> None:
    assert line in CLOUD_INIT


def test_k3s_version_is_pinned() -> None:
    assert 'K3S_VERSION="${k3s_version}"' in CLOUD_INIT
    assert re.search(r'default\s+= "v\d+\.\d+\.\d+\+k3s\d+"', tf("variables.tf"))
    assert "get.k3s.io" not in CLOUD_INIT


def test_cloud_init_carries_no_secret() -> None:
    # Only one template variable may reach user_data, and it is a public version string.
    assert set(re.findall(r"\$\{(\w+)\}", CLOUD_INIT)) == {"k3s_version"}
    assert not re.search(r"(?i)(token|password|secret|api_key)\s*=", CLOUD_INIT)
