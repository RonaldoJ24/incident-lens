"""Optional PySpark implementation of the Phase 2 offline pipeline.

Spark is imported only when this job is invoked. Canonical event creation is
delegated to the portable normalizer inside a small UDF, so timestamp units,
nanosecond rendering, leakage rules, event IDs, deduplication, and quality
hashes cannot drift between the two offline paths.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from incident_lens.pipeline.normalization import (
    LeakageError,
    NORMALIZATION_VERSION,
    NormalizationError,
    TimestampError,
    _event_from_record,
    canonical_json,
)


class SparkUnavailableError(RuntimeError):
    """Raised when the optional Spark runtime is not installed/usable."""


_NEUTRAL_CASE = re.compile(r"^dev-re2ob-\d{3}$")
_UPSTREAM_CASE = re.compile(r"re[123](?:ob|ss|tt)_[a-z0-9-]+_(?:cpu|mem|disk|delay|loss|socket|f[1-5])_\d+", re.IGNORECASE)


def _manifest_hash(document: Dict[str, Any]) -> str:
    deterministic = dict(document)
    deterministic.pop("generated_at", None)
    return hashlib.sha256(canonical_json(deterministic).encode("utf-8")).hexdigest()


def run_spark_normalization(
    input_root: Path,
    output_root: Path,
    *,
    case_id: str,
    split: str,
    source_version: str,
    dataset_revision: str,
    app_name: str = "incident-lens-phase2-normalize",
) -> Dict[str, Any]:
    """Normalize one neutral case with Spark and return its safe manifest.

    ``input_root`` must be a private directory named with the neutral case ID.
    Only logs/metrics/traces parquet files are read; the hidden injection-time
    file is deliberately not part of this pipeline.
    """

    if not _NEUTRAL_CASE.fullmatch(case_id):
        raise ValueError("case ID must be neutral")
    if split != "development":
        raise ValueError("Spark normalization accepts the development split only")
    if input_root.name != case_id or _UPSTREAM_CASE.search(str(input_root)):
        raise ValueError("Spark input must be a neutral case directory")
    try:
        from pyspark.sql import SparkSession, functions as F, types as T
    except ImportError as exc:
        raise SparkUnavailableError("pyspark is not installed; run this job in the Spark CI environment") from exc

    existing_session = SparkSession.getActiveSession()
    spark = SparkSession.builder.appName(app_name).getOrCreate()
    owns_session = existing_session is None
    try:
        signal_summaries = []
        for signal in ("logs", "metrics", "traces"):
            path = input_root / (signal + ".parquet")
            if not path.exists():
                signal_summaries.append({"signal": signal, "input_count": 0, "output_count": 0, "duplicate_count": 0, "malformed_count": 0, "first_event_time": None, "last_event_time": None, "sha256": hashlib.sha256(b"").hexdigest()})
                continue
            frame = spark.read.parquet(str(path))
            input_count = frame.count()
            if input_count == 0:
                output_path = output_root / ("case=%s" % case_id) / ("signal=%s" % signal)
                frame.write.mode("overwrite").parquet(str(output_path))
                signal_summaries.append({"signal": signal, "input_count": 0, "output_count": 0, "duplicate_count": 0, "malformed_count": 0, "first_event_time": None, "last_event_time": None, "sha256": hashlib.sha256(b"").hexdigest()})
                continue
            timestamp_column = next((name for name in ("timestamp", "event_time", "observed_at", "startTimeMillis", "startTime", "start_time", "time") if name in frame.columns), None)
            if not timestamp_column:
                raise ValueError("%s has no timestamp column" % signal)
            original_columns = sorted(frame.columns)
            payload = F.to_json(F.struct(*[F.col(name) for name in original_columns]), {"ignoreNullFields": "false"})
            result_schema = T.StructType([
                T.StructField("event_id", T.StringType(), True),
                T.StructField("timestamp", T.StringType(), True),
                T.StructField("event_json", T.StringType(), True),
                T.StructField("error", T.StringType(), True),
            ])

            def safe_event(value: str) -> Dict[str, Any]:
                try:
                    event = _event_from_record(signal, json.loads(value))
                    return {"event_id": event.event_id, "timestamp": event.timestamp, "event_json": canonical_json(event.as_dict()), "error": None}
                except TimestampError:
                    return {"event_id": None, "timestamp": None, "event_json": None, "error": "timestamp"}
                except LeakageError:
                    return {"event_id": None, "timestamp": None, "event_json": None, "error": "leakage"}
                except NormalizationError:
                    # Keep error details bounded and never return the offending
                    # record to the driver or a manifest.
                    return {"event_id": None, "timestamp": None, "event_json": None, "error": "normalization"}

            event_udf = F.udf(safe_event, result_schema)
            frame = frame.withColumn("__safe_event", event_udf(payload))
            malformed = frame.filter(F.col("__safe_event.error") == "timestamp").count()
            leaked = frame.filter(F.col("__safe_event.error") == "leakage").count()
            other_errors = frame.filter(F.col("__safe_event.error").isNotNull()).count() - malformed - leaked
            if malformed:
                raise ValueError("%s has %d malformed timestamp(s)" % (signal, malformed))
            if leaked or other_errors:
                raise ValueError("%s contains hidden-label or source-filename leakage" % signal)
            frame = frame.select(
                *[F.col(name) for name in original_columns],
                F.col("__safe_event.event_id").alias("__event_id"),
                F.col("__safe_event.timestamp").alias("__timestamp"),
                F.col("__safe_event.event_json").alias("__event_json"),
            )
            frame = frame.withColumn("__sort_timestamp", F.to_timestamp("__timestamp"))
            duplicate_count = input_count - frame.select("__event_id").distinct().count()
            frame = frame.dropDuplicates(["__event_id"]).orderBy(F.col("__sort_timestamp"), F.col("__timestamp"), F.col("__event_id"))
            output_count = frame.count()
            first_time = frame.select("__timestamp").first()["__timestamp"]
            last_time = frame.orderBy(F.col("__sort_timestamp").desc(), F.col("__timestamp").desc(), F.col("__event_id").desc()).select("__timestamp").first()["__timestamp"]
            ordered = F.sort_array(F.collect_list(F.struct("__sort_timestamp", "__timestamp", "__event_id", "__event_json")))
            encoded_events = F.transform(ordered, lambda row: row["__event_json"])
            # Portable normalization hashes canonical JSON plus a trailing
            # newline for every event; preserve that exact framing, including
            # the empty-stream hash.
            encoded = F.when(
                F.size(ordered) == 0,
                F.lit(""),
            ).otherwise(F.concat(F.concat_ws("\n", encoded_events), F.lit("\n")))
            event_digest = frame.select(F.sha2(encoded, 256).alias("digest")).first()["digest"]
            output_path = output_root / ("case=%s" % case_id) / ("signal=%s" % signal)
            frame.write.mode("overwrite").parquet(str(output_path))
            signal_summaries.append({
                "signal": signal,
                "input_count": input_count,
                "output_count": output_count,
                "duplicate_count": duplicate_count,
                "malformed_count": malformed,
                "first_event_time": first_time,
                "last_event_time": last_time,
                "sha256": event_digest or hashlib.sha256(b"").hexdigest(),
            })
        window_times = [time for summary in signal_summaries for time in (summary["first_event_time"], summary["last_event_time"]) if time]
        document: Dict[str, Any] = {
            "manifest_version": "2.0.0",
            "manifest_id": "incident-lens-derived-%s" % case_id,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source": {"source_id": "rcaeval", "dataset": "RCAEval", "subset": "RE2-OB", "source_version": source_version, "dataset_revision": dataset_revision},
            "split": split,
            "case_id": case_id,
            "normalization_version": NORMALIZATION_VERSION,
            "window": {"start": min(window_times) if window_times else None, "end": max(window_times) if window_times else None, "event_count": sum(item["output_count"] for item in signal_summaries)},
            "signals": signal_summaries,
            "license": {"name": "MIT", "url": "https://github.com/phamquiluan/RCAEval/blob/bb48c5aa9a24f1d5fcc716bdd479ea2d63145c90/LICENSE", "redistribution": "raw telemetry remains outside Git"},
            "attribution": "Pham, Luan et al. RCAEval (2025). Derived quality summary generated from a pinned case.",
            "raw_data_in_repo": False,
            "leakage_review": {"neutral_ids": True, "hidden_labels_removed": True, "source_filenames_removed": True, "review_status": "passed"},
        }
        document["manifest_hash"] = _manifest_hash(document)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / ("manifest-%s.json" % case_id)).write_text(canonical_json(document) + "\n", encoding="utf-8")
        return document
    finally:
        if owns_session:
            spark.stop()


__all__ = ["SparkUnavailableError", "run_spark_normalization"]
