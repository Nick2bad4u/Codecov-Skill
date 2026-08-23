# Copyright (c) 2026 Nick2bad4u

from __future__ import annotations

import math
import re
import time
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast
from xml.etree import ElementTree as ET

from codecov_manage_common import CodecovCliError

if TYPE_CHECKING:
    from codecov_manage_api import CodecovContext

JsonObject = dict[str, Any]

MAX_REPORT_BYTES = 100 * 1024 * 1024
MAX_PATH_SAMPLES = 25
MAX_REPORT_AGE_SECONDS = 12 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60
MILLISECOND_TIMESTAMP_THRESHOLD = 100_000_000_000
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:/")
UNSAFE_XML_MARKERS = (b"<!doctype", b"<!entity")


def inspect_coverage_report(
    *,
    context: CodecovContext,
    report_path: Path,
    now_timestamp: float | None = None,
) -> JsonObject:
    resolved_report = resolve_repo_report_path(context.repo_root, report_path)
    reject_unsafe_or_oversized_xml(resolved_report)
    timestamp, filenames = parse_cobertura_report(resolved_report)
    path_analysis = analyze_report_paths(context.repo_root, filenames)
    timestamp_analysis = analyze_report_timestamp(timestamp, now_timestamp=now_timestamp)

    path_issues = path_analysis.pop("issues")
    timestamp_issues = timestamp_analysis.pop("issues")
    if not isinstance(path_issues, list) or not isinstance(timestamp_issues, list):  # pragma: no cover
        raise CodecovCliError("Internal coverage report inspection result was malformed.")
    issues = [*cast("list[str]", path_issues), *cast("list[str]", timestamp_issues)]
    return {
        "repoRoot": str(context.repo_root),
        "reportPath": resolved_report.relative_to(context.repo_root.resolve()).as_posix(),
        "format": "cobertura",
        "timestamp": timestamp_analysis,
        "files": path_analysis,
        "readyForUpload": not issues,
        "issues": issues,
    }


def resolve_repo_report_path(repo_root: Path, report_path: Path) -> Path:
    resolved_root = repo_root.resolve()
    candidate = report_path if report_path.is_absolute() else resolved_root / report_path
    resolved_candidate = candidate.resolve()

    try:
        _ = resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise CodecovCliError("Coverage report path must resolve inside the target repository.") from error

    if not resolved_candidate.is_file():
        raise CodecovCliError(f"Coverage report does not exist or is not a file: {report_path}")

    return resolved_candidate


def reject_unsafe_or_oversized_xml(report_path: Path) -> None:
    report_size = report_path.stat().st_size
    if report_size > MAX_REPORT_BYTES:
        raise CodecovCliError(
            f"Coverage report exceeds the {MAX_REPORT_BYTES}-byte inspection limit: {report_path.name}"
        )

    previous_tail = b""
    with report_path.open("rb") as report_stream:
        while chunk := report_stream.read(64 * 1024):
            searchable = (previous_tail + chunk).lower()
            if any(marker in searchable for marker in UNSAFE_XML_MARKERS):
                raise CodecovCliError("Coverage report contains a forbidden XML document type or entity declaration.")
            previous_tail = searchable[-16:]


def parse_cobertura_report(report_path: Path) -> tuple[str | None, list[str]]:
    try:
        events = ET.iterparse(  # noqa: S314 - the local XML is path-constrained, size-bounded, and pre-screened.
            report_path,
            events=("start",),
        )
        _, root = next(events)
        if local_name(root.tag) != "coverage":
            raise CodecovCliError("Coverage report root must be a Cobertura <coverage> element.")

        timestamp = root.attrib.get("timestamp")
        filenames: list[str] = []
        for _, element in events:
            if local_name(element.tag) == "class":
                filenames.append(element.attrib.get("filename", ""))
    except (ET.ParseError, StopIteration) as error:
        raise CodecovCliError(f"Coverage report is not valid Cobertura XML: {report_path.name}") from error

    return timestamp, filenames


def local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def analyze_report_paths(repo_root: Path, filenames: list[str]) -> JsonObject:
    resolved_root = repo_root.resolve()
    unique_filenames = list(dict.fromkeys(filenames))
    samples: dict[str, list[str]] = {
        "empty": [],
        "absolute": [],
        "parentTraversal": [],
        "windowsSeparators": [],
        "outsideRepository": [],
        "missing": [],
        "basenameOnly": [],
    }
    counts = dict.fromkeys(samples, 0)
    existing_count = 0

    for raw_filename in unique_filenames:
        category, exists = classify_report_path(resolved_root, raw_filename)
        if exists:
            existing_count += 1
        if category is None:
            continue

        for category_name in category:
            counts[category_name] += 1
            append_sample(samples[category_name], raw_filename)

    blocking_categories = (
        "empty",
        "absolute",
        "parentTraversal",
        "windowsSeparators",
        "outsideRepository",
        "missing",
    )
    issues = [f"coverage-path-{name}" for name in blocking_categories if counts[name]]
    if not unique_filenames:
        issues.append("coverage-report-has-no-class-paths")

    return {
        "classElements": len(filenames),
        "uniqueFilenames": len(unique_filenames),
        "existingRepositoryFiles": existing_count,
        "pathMappingReady": not issues,
        "issueCounts": counts,
        "samples": samples,
        "issues": issues,
    }


def classify_report_path(repo_root: Path, raw_filename: str) -> tuple[tuple[str, ...] | None, bool]:
    stripped = raw_filename.strip()
    if not stripped:
        return ("empty",), False

    normalized = stripped.replace("\\", "/")
    categories: list[str] = []
    if "\\" in stripped:
        categories.append("windowsSeparators")
    if PurePosixPath(normalized).is_absolute() or WINDOWS_DRIVE_PATH.match(normalized):
        categories.append("absolute")
        return tuple(categories), False

    path_parts = PurePosixPath(normalized).parts
    if ".." in path_parts:
        categories.append("parentTraversal")
        return tuple(categories), False
    if len(path_parts) == 1:
        categories.append("basenameOnly")

    candidate = (repo_root / Path(*path_parts)).resolve()
    try:
        _ = candidate.relative_to(repo_root)
    except ValueError:
        categories.append("outsideRepository")
        return tuple(categories), False

    exists = candidate.is_file()
    if not exists:
        categories.append("missing")
    return tuple(categories) or None, exists


def append_sample(samples: list[str], value: str) -> None:
    if len(samples) < MAX_PATH_SAMPLES:
        samples.append(value)


def analyze_report_timestamp(raw_timestamp: str | None, *, now_timestamp: float | None) -> JsonObject:
    if raw_timestamp is None or not raw_timestamp.strip():
        return {
            "present": False,
            "issues": [],
        }

    stripped = raw_timestamp.strip()
    try:
        numeric_timestamp = float(stripped)
    except ValueError:
        return {
            "present": True,
            "raw": stripped,
            "numeric": False,
            "issues": ["coverage-timestamp-not-numeric"],
        }

    if not math.isfinite(numeric_timestamp):
        return {
            "present": True,
            "raw": stripped,
            "numeric": False,
            "issues": ["coverage-timestamp-not-finite"],
        }

    unit = "milliseconds" if abs(numeric_timestamp) >= MILLISECOND_TIMESTAMP_THRESHOLD else "seconds"
    unix_seconds = numeric_timestamp / 1000 if unit == "milliseconds" else numeric_timestamp
    current_timestamp = time.time() if now_timestamp is None else now_timestamp
    age_seconds = current_timestamp - unix_seconds
    issues: list[str] = []
    if age_seconds > MAX_REPORT_AGE_SECONDS:
        issues.append("coverage-timestamp-older-than-12-hours")
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        issues.append("coverage-timestamp-too-far-in-future")

    try:
        iso_utc = datetime.fromtimestamp(unix_seconds, tz=UTC).isoformat()
    except (OSError, OverflowError, ValueError) as error:
        raise CodecovCliError(f"Coverage report timestamp is outside the supported date range: {stripped}") from error

    return {
        "present": True,
        "raw": stripped,
        "numeric": True,
        "unit": unit,
        "unixSeconds": unix_seconds,
        "isoUtc": iso_utc,
        "ageSeconds": round(age_seconds, 3),
        "olderThan12Hours": age_seconds > MAX_REPORT_AGE_SECONDS,
        "issues": issues,
    }
