"""CLI for integrity-checking a Phase 3 artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from .artifacts import ArtifactError, verify_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a Phase 3 ranking artifact")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        document = verify_artifact(args.path)
    except ArtifactError as exc:
        parser.error(str(exc))
    print("verified %s: method=%s feature_schema=%s" % (args.path, document["method"], document["feature_schema_version"]))


if __name__ == "__main__":
    main()
