"""Strip identifiers from Terraform and OCI output before it is written anywhere shareable.

OCIDs, public IPs and the Object Storage namespace are not secrets in the strict sense,
but together they map the tenancy for an attacker, so proofs and logs never carry them.
"""

from __future__ import annotations

import re

_OCID = re.compile(r"ocid1\.[a-z0-9._-]+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")
# Object Storage paths look like n/<namespace>/b/<bucket>.
_NAMESPACE = re.compile(r"\bn/[a-z0-9]+/b/")
_REQUEST_ID = re.compile(r"(OPC request ID:|opc-request-id:?)\s*\S+", re.IGNORECASE)

# Private and wildcard ranges describe our own VCN layout, already public in the Terraform
# code, and hiding them would make the proofs unreadable.
_KEEP_IP_PREFIXES = ("10.", "127.", "0.")


def _mask_public_ip(match: re.Match[str]) -> str:
    value = match.group(0)
    return value if value.startswith(_KEEP_IP_PREFIXES) else "<ip>"


def redact(text: str) -> str:
    text = _OCID.sub("<ocid>", text)
    text = _IPV4.sub(_mask_public_ip, text)
    text = _NAMESPACE.sub("n/<namespace>/b/", text)
    return _REQUEST_ID.sub(r"\1 <redacted>", text)
