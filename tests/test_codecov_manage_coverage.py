# Copyright (c) 2026 Nick2bad4u

from __future__ import annotations

from pathlib import Path

import pytest
from codecov_manage_api import CodecovContext
from codecov_manage_common import CodecovCliError
from codecov_manage_coverage import inspect_coverage_report


def make_context(repo_root: Path) -> CodecovContext:
    return CodecovContext(
        repo_root=repo_root,
        service="github",
        owner="Nick2bad4u",
        repo_name="Codecov-Skill",
        base_url="https://api.codecov.io",
        token=None,
        token_env_name=None,
        codecov_yml_path=None,
    )


def write_report(report_path: Path, *, timestamp: str, filenames: list[str]) -> None:
    class_elements = "\n".join(
        f'<class name="file-{index}" filename="{filename}" />' for index, filename in enumerate(filenames)
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _ = report_path.write_text(
        f"""<?xml version="1.0" ?>
<coverage timestamp="{timestamp}">
  <packages>
    <package name="example">
      <classes>
        {class_elements}
      </classes>
    </package>
  </packages>
</coverage>
""",
        encoding="utf8",
    )


def test_inspect_coverage_report_accepts_current_milliseconds_and_repo_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    source_file = repo_root / "skills" / "example" / "scripts" / "tool.py"
    source_file.parent.mkdir(parents=True)
    _ = source_file.write_text("print('ok')\n", encoding="utf8")
    report_path = repo_root / "coverage" / "python.xml"
    write_report(
        report_path,
        timestamp="1799996400000",
        filenames=["skills/example/scripts/tool.py"],
    )

    payload = inspect_coverage_report(
        context=make_context(repo_root),
        report_path=Path("coverage/python.xml"),
        now_timestamp=1_800_000_000,
    )

    assert payload["readyForUpload"] is True
    assert payload["issues"] == []
    assert payload["timestamp"]["unit"] == "milliseconds"
    assert payload["timestamp"]["olderThan12Hours"] is False
    assert payload["files"]["pathMappingReady"] is True
    assert payload["files"]["existingRepositoryFiles"] == 1


def test_inspect_coverage_report_explains_stale_and_unmappable_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report_path = repo_root / "coverage.xml"
    write_report(
        report_path,
        timestamp=str(1_800_000_000 - (13 * 60 * 60)),
        filenames=[
            "tool.py",
            "C:\\runner\\repo\\tool.py",
            "../outside.py",
            "skills/example/scripts/missing.py",
        ],
    )

    payload = inspect_coverage_report(
        context=make_context(repo_root),
        report_path=Path("coverage.xml"),
        now_timestamp=1_800_000_000,
    )

    assert payload["readyForUpload"] is False
    assert "coverage-timestamp-older-than-12-hours" in payload["issues"]
    assert "coverage-path-missing" in payload["issues"]
    assert "coverage-path-absolute" in payload["issues"]
    assert "coverage-path-parentTraversal" in payload["issues"]
    assert payload["files"]["issueCounts"]["basenameOnly"] == 1


def test_inspect_coverage_report_rejects_paths_outside_repository(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report_path = tmp_path / "outside.xml"
    write_report(report_path, timestamp="1800000000", filenames=["source.py"])

    with pytest.raises(CodecovCliError, match="inside the target repository"):
        _ = inspect_coverage_report(
            context=make_context(repo_root),
            report_path=report_path,
            now_timestamp=1_800_000_000,
        )


def test_inspect_coverage_report_rejects_unsafe_xml_declarations(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report_path = repo_root / "coverage.xml"
    _ = report_path.write_text(
        '<!DOCTYPE coverage [<!ENTITY external SYSTEM "file:///etc/passwd">]><coverage />',
        encoding="utf8",
    )

    with pytest.raises(CodecovCliError, match="forbidden XML"):
        _ = inspect_coverage_report(
            context=make_context(repo_root),
            report_path=Path("coverage.xml"),
            now_timestamp=1_800_000_000,
        )
