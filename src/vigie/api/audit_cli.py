"""Audit log maintenance from the command line.

    python -m vigie.api.audit_cli verify    check the hash chain of this pod's files
    python -m vigie.api.audit_cli purge     delete the days past the retention period

The API purges on its own on the first write of each day; the command is for the
runbook and for backups, which must follow the same 30 days.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from vigie.api.audit import AuditLog, verify_chain
from vigie.config import get_settings


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m vigie.api.audit_cli", description=__doc__)
    parser.add_argument("command", choices=["verify", "purge"])
    args = parser.parse_args(argv)

    settings = get_settings()
    log = AuditLog(settings.audit_dir, settings.audit_pod_name, settings.audit_retention_days)
    if args.command == "purge":
        removed = log.purge()
        out.write(
            f"purged {len(removed)} file(s) older than {settings.audit_retention_days} days\n"
        )
        return 0
    report = verify_chain(log.directory)
    if report.ok:
        out.write(f"chain intact, {report.lines} line(s)\n")
        return 0
    out.write(f"chain broken after {report.lines} line(s): {report.error}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
