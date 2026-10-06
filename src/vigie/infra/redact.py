"""Strip identifiers from Terraform and OCI output before it is written anywhere shareable.

OCIDs, public IPs, the Object Storage namespace or the tenancy prefix of an availability
domain are not secrets in the strict sense, but together they map the tenancy for an
attacker, so proofs and logs never carry them. A plan also prints the alert e-mail and
the SSH public key, which identify a person.
"""

from __future__ import annotations

import re

_OCID = re.compile(r"ocid1\.[a-z0-9._-]+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")
# Object Storage shows the namespace both in paths (n/<ns>/b/<bucket>) and as an attribute.
_NAMESPACE_PATH = re.compile(r"\bn/[a-z0-9]+/b/")
_NAMESPACE_ATTR = re.compile(r'(\bnamespace\s*=\s*)"[a-z0-9]+"')
# Availability domain names carry a per-tenancy prefix, as in "AbCd:EU-PARIS-1-AD-1".
_AD_PREFIX = re.compile(r"\b[A-Za-z0-9]{4}:([A-Z0-9-]+-AD-\d)\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_SSH_KEY = re.compile(r"\b(ssh-(?:ed25519|rsa)|ecdsa-sha2-nistp\d+) [A-Za-z0-9+/=]+(?: [^\s\"]+)?")
_REQUEST_ID = re.compile(r"(OPC request ID:|opc-request-id:?)\s*\S+", re.IGNORECASE)

# Private and wildcard ranges describe our own VCN layout, already public in the Terraform
# code, and hiding them would make the proofs unreadable.
_KEEP_IP_PREFIXES = ("10.", "127.", "0.")


def _mask_public_ip(match: re.Match[str]) -> str:
    value = match.group(0)
    return value if value.startswith(_KEEP_IP_PREFIXES) else "<ip>"


def redact(text: str) -> str:
    text = _OCID.sub("<ocid>", text)
    text = _SSH_KEY.sub(r"\1 <public-key>", text)
    text = _EMAIL.sub("<email>", text)
    text = _IPV4.sub(_mask_public_ip, text)
    text = _NAMESPACE_PATH.sub("n/<namespace>/b/", text)
    text = _NAMESPACE_ATTR.sub(r'\1"<namespace>"', text)
    text = _AD_PREFIX.sub(r"<prefix>:\1", text)
    return _REQUEST_ID.sub(r"\1 <redacted>", text)
