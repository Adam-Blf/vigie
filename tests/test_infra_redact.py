from vigie.infra.redact import redact


def test_ocids_are_masked() -> None:
    text = "id=ocid1.instance.oc1.eu-paris-1.anwhqljrabcdef tenancy ocid1.tenancy.oc1..aaaaxyz"
    assert redact(text) == "id=<ocid> tenancy <ocid>"


def test_public_ips_are_masked_but_private_ranges_stay() -> None:
    text = "public 81.2.69.160 admin 81.2.69.1/32 vcn 10.10.0.0/16 any 0.0.0.0/0 lo 127.0.0.1"
    assert redact(text) == "public <ip> admin <ip> vcn 10.10.0.0/16 any 0.0.0.0/0 lo 127.0.0.1"


def test_namespace_and_request_id_are_masked() -> None:
    text = "[id=n/axrsabcdef/b/vigie-backups/l]\nOPC request ID: 7f86c1d5/737D83A0"
    assert redact(text) == "[id=n/<namespace>/b/vigie-backups/l]\nOPC request ID: <redacted>"


def test_plan_attributes_that_identify_the_tenancy_are_masked() -> None:
    text = (
        '+ availability_domain = "TYWr:EU-PARIS-1-AD-1"\n'
        '+ namespace    = "axrsabcdef"\n'
        '+ recipients     = "jane.doe@example.org"\n'
        '+ "ssh_authorized_keys" = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabc+/= vigie-deploy"'
    )
    assert redact(text) == (
        '+ availability_domain = "<prefix>:EU-PARIS-1-AD-1"\n'
        '+ namespace    = "<namespace>"\n'
        '+ recipients     = "<email>"\n'
        '+ "ssh_authorized_keys" = "ssh-ed25519 <public-key>"'
    )


def test_plain_text_is_untouched() -> None:
    assert redact("Apply complete! Resources: 1 added.") == "Apply complete! Resources: 1 added."
