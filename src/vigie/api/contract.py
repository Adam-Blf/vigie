"""Writes the API contract to docs/openapi.json, or checks that it is current.

    python -m vigie.api.contract           regenerate docs/openapi.json
    python -m vigie.api.contract --check   fail if the file differs from the code

The interface and its mock API are built against that file, so it is versioned with the
code and a test fails as soon as the two disagree.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vigie.api.app import base_app

CONTRACT_PATH = Path("docs/openapi.json")


def openapi_document() -> dict[str, Any]:
    return base_app().openapi()


def render() -> str:
    return json.dumps(openapi_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None, path: Path = CONTRACT_PATH) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    expected = render()
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if "--check" in args:
        if current != expected:
            print(f"{path.as_posix()} is out of date, run: python -m vigie.api.contract")
            return 1
        return 0
    path.write_text(expected, encoding="utf-8")
    print(f"wrote {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
