"""Load the reviewed authored fixture without reaching an external source."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    title: str
    description: str
    service: str
    source_interval_payload: Dict[str, Any]
    events: List[Dict[str, Any]]
    fixture_kind: str


def load_cases() -> List[FixtureCase]:
    path = Path(__file__).with_name("cases.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    version = document["fixture_version"]
    kind = document["fixture_kind"]
    result: List[FixtureCase] = []
    for item in document["cases"]:
        signals = {event["signal"] for event in item["events"]}
        completeness = {
            signal: "available" if signal in signals else "missing"
            for signal in ("logs", "metrics", "traces")
        }
        interval = {
            **item["source_interval"],
            "case_or_upload_id": item["case_id"],
            "source_version": version,
            "signal_completeness": completeness,
        }
        result.append(
            FixtureCase(
                case_id=item["case_id"],
                title=item["title"],
                description=item["description"],
                service=item["service"],
                source_interval_payload=interval,
                events=item["events"],
                fixture_kind=kind,
            )
        )
    return result
