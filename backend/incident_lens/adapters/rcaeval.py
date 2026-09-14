"""RCAEval source adapter with a private raw-data boundary.

The public development manifest contains only neutral case IDs.  The mapping
from a neutral ID to the upstream directory (which encodes the answer) is
loaded from a protected locator file and is never returned by this module's
public result objects.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import argparse
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RCAEvalSourceRevision = "bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90"
RCAEvalDatasetRevision = "afeacb11bcc94dadfd1c8f483ee4377b2b8b614e"
RCAEvalRepository = "https://github.com/phamquiluan/RCAEval"
RCAEvalDatasetURL = "https://huggingface.co/datasets/phamquiluan/RCAEval"
RCAEvalDataset = "RE2-OB"
RCAEvalSplit = "development"

_CASE_ID = re.compile(r"^dev-re2ob-\d{3}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_FILES = ("metrics.parquet", "logs.parquet", "traces.parquet", "inject_time.txt")


class SourceAdapterError(ValueError):
    """Raised when a source locator or upstream artifact is unsafe."""


class SourceArtifactNotFound(SourceAdapterError):
    """Raised only for an optional signal absent from an upstream case."""


@dataclass(frozen=True)
class SourceLocator:
    """Private mapping held outside Git; ``remote_case`` is never public."""

    case_id: str
    remote_case: str
    dataset: str = RCAEvalDataset
    split: str = RCAEvalSplit
    source_revision: str = RCAEvalSourceRevision
    dataset_revision: str = RCAEvalDatasetRevision

    def __post_init__(self) -> None:
        if not _CASE_ID.fullmatch(self.case_id):
            raise SourceAdapterError("source locator must use a neutral case ID")
        if self.dataset != RCAEvalDataset or self.split != RCAEvalSplit:
            raise SourceAdapterError("locator is outside the permitted development split")
        if not _REVISION.fullmatch(self.source_revision):
            raise SourceAdapterError("source revision must be a pinned commit")
        if not _REVISION.fullmatch(self.dataset_revision):
            raise SourceAdapterError("dataset revision must be a pinned commit")
        if not re.fullmatch(r"re2ob_[a-z0-9-]+_(?:cpu|mem|disk|delay|loss|socket)_\d+", self.remote_case):
            raise SourceAdapterError("remote case locator is not a RE2-OB case")


@dataclass(frozen=True)
class RawFile:
    signal: str
    sha256: str
    byte_size: int
    object_key: str


@dataclass(frozen=True)
class RawCase:
    """Fetched raw files and safe metadata.  No upstream path is exposed."""

    case_id: str
    source_revision: str
    dataset_revision: str
    files: Tuple[RawFile, ...]
    raw_root: Path

    @property
    def available_signals(self) -> Tuple[str, ...]:
        return tuple(item.signal for item in self.files if item.signal in {"logs", "metrics", "traces"})


def _safe_locator_file(path: Path) -> None:
    """Require a private, ignored locator file rather than an in-repo mapping."""

    resolved = path.resolve()
    project_root = Path.cwd().resolve()
    in_project = str(resolved) == str(project_root) or str(resolved).startswith(str(project_root) + "/")
    if in_project and "/data/raw/" not in str(resolved) and "/data/cache/" not in str(resolved):
        raise SourceAdapterError("source locator must be under ignored data/raw or data/cache")


def load_source_locators(path: Optional[Path] = None) -> Dict[str, SourceLocator]:
    """Load protected locators from ``INCIDENT_LENS_SOURCE_LOCATOR_FILE``.

    The default points at an ignored path.  No fallback locator is invented,
    because silently guessing an upstream path could expose the benchmark
    answer through a public identifier.
    """

    configured = path or Path(os.getenv("INCIDENT_LENS_SOURCE_LOCATOR_FILE", "data/raw/rcaeval/source-locators.json"))
    _safe_locator_file(configured)
    try:
        document = json.loads(configured.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceAdapterError("protected RCAEval source locator file is unavailable") from exc
    if not isinstance(document, dict) or not isinstance(document.get("locators"), dict):
        raise SourceAdapterError("locator file must contain a locators object")
    result: Dict[str, SourceLocator] = {}
    for case_id, item in document["locators"].items():
        if not isinstance(item, dict):
            raise SourceAdapterError("locator entries must be objects")
        if case_id != item.get("case_id"):
            raise SourceAdapterError("locator key and neutral case ID differ")
        locator = SourceLocator(**item)
        if locator.case_id in result:
            raise SourceAdapterError("duplicate neutral case locator")
        result[locator.case_id] = locator
    return result


def _download(url: str, timeout: float, max_bytes: int, retries: int = 2) -> bytes:
    request = Request(url, headers={"User-Agent": "incident-lens/phase2"})
    if max_bytes <= 0:
        raise SourceAdapterError("maximum artifact size must be positive")
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise SourceAdapterError("RCAEval artifact exceeds the offline size limit")
                return content
        except HTTPError as exc:
            if exc.code == 404:
                raise SourceArtifactNotFound("RCAEval artifact is absent") from exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt == retries:
                raise SourceAdapterError("RCAEval artifact could not be fetched") from exc
        except (URLError, TimeoutError) as exc:
            if attempt == retries:
                raise SourceAdapterError("RCAEval artifact could not be fetched") from exc
        time.sleep(min(0.25 * (2**attempt), 1.0))
    raise SourceAdapterError("RCAEval artifact could not be fetched")


class RCAEvalAdapter:
    """Fetch one pinned case at a time into an ignored raw-data directory."""

    def __init__(
        self,
        raw_root: Path = Path("data/raw/rcaeval"),
        source_revision: str = RCAEvalSourceRevision,
        dataset_revision: str = RCAEvalDatasetRevision,
        timeout: float = 30.0,
        max_file_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        if not _REVISION.fullmatch(source_revision) or not _REVISION.fullmatch(dataset_revision):
            raise SourceAdapterError("RCAEval revisions must be pinned commits")
        if max_file_bytes <= 0:
            raise SourceAdapterError("maximum artifact size must be positive")
        self.raw_root = raw_root
        self.source_revision = source_revision
        self.dataset_revision = dataset_revision
        self.timeout = timeout
        self.max_file_bytes = max_file_bytes

    def fetch_case(self, locator: SourceLocator) -> RawCase:
        if locator.source_revision != self.source_revision or locator.dataset_revision != self.dataset_revision:
            raise SourceAdapterError("locator revision does not match the adapter pin")
        if locator.dataset != RCAEvalDataset or locator.split != RCAEvalSplit:
            raise SourceAdapterError("only RE2-OB development locators are allowed")
        case_root = self.raw_root / locator.case_id
        case_root.mkdir(parents=True, exist_ok=True)
        files = []
        for filename in _ALLOWED_FILES:
            # The upstream case path is private and is used only in this URL.
            url = "%s/resolve/%s/%s/%s" % (RCAEvalDatasetURL, self.dataset_revision, locator.remote_case, filename)
            try:
                content = _download(url, self.timeout, self.max_file_bytes)
            except SourceArtifactNotFound:
                if filename in {"logs.parquet", "traces.parquet"}:
                    continue
                raise
            digest = hashlib.sha256(content).hexdigest()
            destination = case_root / filename
            # Avoid partial raw files if the process is interrupted.
            with tempfile.NamedTemporaryFile(dir=str(case_root), delete=False) as temporary:
                temporary.write(content)
                temporary_path = Path(temporary.name)
            temporary_path.replace(destination)
            signal = filename.split(".", 1)[0]
            key = "raw/rcaeval/%s/%s/%s" % (self.source_revision, locator.case_id, filename)
            files.append(RawFile(signal=signal, sha256=digest, byte_size=len(content), object_key=key))
        if not any(item.signal == "metrics" for item in files):
            raise SourceAdapterError("RCAEval case has no metrics artifact")
        return RawCase(
            case_id=locator.case_id,
            source_revision=self.source_revision,
            dataset_revision=self.dataset_revision,
            files=tuple(files),
            raw_root=case_root,
        )


# Friendly spelling for callers that use normal title casing.
RcaEvalAdapter = RCAEvalAdapter


def raw_case_metadata(case: RawCase) -> Mapping[str, object]:
    """Return a safe metadata record suitable for a public quality report."""

    return {
        "case_id": case.case_id,
        "source_id": "rcaeval",
        "dataset": RCAEvalDataset,
        "source_version": "RCAEval@" + case.source_revision,
        "dataset_revision": "RCAEval-HF@" + case.dataset_revision,
        "signals": list(case.available_signals),
        "files": [
            {"signal": item.signal, "sha256": item.sha256, "byte_size": item.byte_size, "object_key": item.object_key}
            for item in case.files
            if item.signal in {"logs", "metrics", "traces"}
        ],
        "raw_data_in_repo": False,
    }


def fetch_case(
    case_id: str,
    *,
    locator_file: Optional[Path] = None,
    raw_root: Path = Path("data/raw/rcaeval"),
) -> RawCase:
    """Convenience entry point that keeps the protected lookup server-side."""

    locators = load_source_locators(locator_file)
    try:
        locator = locators[case_id]
    except KeyError as exc:
        raise SourceAdapterError("no protected locator for requested neutral case") from exc
    return RCAEvalAdapter(raw_root).fetch_case(locator)


__all__ = [
    "RCAEvalAdapter",
    "RcaEvalAdapter",
    "RCAEvalDataset",
    "RCAEvalDatasetRevision",
    "RCAEvalDatasetURL",
    "RCAEvalRepository",
    "RCAEvalSourceRevision",
    "RawCase",
    "RawFile",
    "SourceArtifactNotFound",
    "SourceAdapterError",
    "SourceLocator",
    "load_source_locators",
    "fetch_case",
    "raw_case_metadata",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one pinned RCAEval case into private raw storage")
    parser.add_argument("--case-id", required=True, help="neutral dev-re2ob-NNN identifier")
    parser.add_argument("--locator-file", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/rcaeval"))
    args = parser.parse_args()
    locators = load_source_locators(args.locator_file)
    if args.case_id not in locators:
        raise SystemExit("no protected locator for requested neutral case")
    case = RCAEvalAdapter(args.raw_root).fetch_case(locators[args.case_id])
    print(json.dumps(raw_case_metadata(case), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
