"""Repository-local link and privacy checks for foundation handoff evidence."""

import argparse
import re
from pathlib import Path
from typing import Iterable, List, Tuple


class LocalCheckError(ValueError):
    """Raised when a local link or privacy boundary is violated."""


_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_PRIVATE_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key material"),
    (re.compile(r"(?:^|\s)(?:sk|rk)-[A-Za-z0-9]{16,}"), "provider credential"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "API key material"),
    (re.compile(r"(?:^|\s)(?:file://|/Users/|/home/|C:\\\\Users\\\\)"), "machine-specific path"),
)
_SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", ".venv"}


def _markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() in {".md", ".markdown"}:
            yield path
        elif path.is_dir():
            for child in path.rglob("*.md"):
                if not any(part in _SKIP_DIRS for part in child.parts):
                    yield child


def check_links(paths: Iterable[Path]) -> List[str]:
    errors: List[str] = []
    for markdown in _markdown_files(paths):
        text = markdown.read_text(encoding="utf-8")
        for target in _MARKDOWN_LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = target.split("#", 1)[0]
            candidate = (markdown.parent / target_path).resolve()
            if not candidate.exists():
                errors.append("%s -> missing %s" % (markdown, target))
    return errors


def _text_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and not any(part in _SKIP_DIRS for part in child.parts):
                    yield child


def check_privacy(paths: Iterable[Path]) -> List[str]:
    errors: List[str] = []
    for path in _text_files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in _PRIVATE_PATTERNS:
            if pattern.search(text):
                errors.append("%s: %s" % (path, label))
    for path in paths:
        if path.is_dir() and path.name in {"raw", "uploads", "derived", "artifacts", "secrets"} and any(path.iterdir()):
            errors.append("%s: generated/private data must stay outside Git" % path)
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check local links and privacy boundaries")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    errors = check_links(args.paths) + check_privacy(args.paths)
    if errors:
        raise SystemExit("\n".join(errors))
    print("local link/privacy checks passed")
