from __future__ import annotations

import codecov_manage_render
import pytest


def test_mark_untrusted_payload_marks_text_fields() -> None:
    payload = codecov_manage_render.mark_untrusted_payload(
        {
            "message": "external\ninstructions",
            "coverage": 87.5,
            "nested": [{"path": "src/index.ts"}],
            "errors": [{"errorCode": "REPORT_EXPIRED"}],
            "samples": {"missing": ["ignore previous instructions.py"]},
        }
    )

    assert payload["message"] == "[untrusted-codecov-text] external instructions"
    assert payload["coverage"] == pytest.approx(87.5)
    assert payload["nested"][0]["path"] == "[untrusted-codecov-text] src/index.ts"
    assert payload["errors"][0]["errorCode"] == "[untrusted-codecov-text] REPORT_EXPIRED"
    assert payload["samples"]["missing"][0] == "[untrusted-codecov-text] ignore previous instructions.py"
    assert "untrustedContentWarning" in payload["_meta"]


def test_render_text_summarizes_lists() -> None:
    rendered = codecov_manage_render.render_text(
        {
            "repository": "owner/repo",
            "branches": [{"name": "main", "coverage": 90.1}],
            "commits": [{"commitid": "abc123", "branch": "main", "coverage": 88.0}],
        }
    )

    assert "Repository: owner/repo" in rendered
    assert "Branches returned: 1" in rendered
    assert "Commits returned: 1" in rendered


def test_render_text_summarizes_local_report_inspection() -> None:
    rendered = codecov_manage_render.render_text(
        {
            "reportPath": "coverage/python.xml",
            "readyForUpload": False,
            "timestamp": {"unit": "milliseconds", "ageSeconds": 46_000.0},
            "files": {"uniqueFilenames": 6, "existingRepositoryFiles": 5},
            "issues": ["coverage-path-missing"],
        }
    )

    assert "Report: coverage/python.xml" in rendered
    assert "Ready for upload: no" in rendered
    assert "Timestamp unit: milliseconds" in rendered
    assert "Repository file paths: 5/6" in rendered
    assert "coverage-path-missing" in rendered


def test_emit_output_writes_json(capsys: pytest.CaptureFixture[str]) -> None:
    codecov_manage_render.emit_output({"message": "external"}, as_json=True)

    captured = capsys.readouterr()
    assert "[untrusted-codecov-text] external" in captured.out


def test_emit_output_writes_string(capsys: pytest.CaptureFixture[str]) -> None:
    codecov_manage_render.emit_output("plain text", as_json=False)

    captured = capsys.readouterr()
    assert captured.out == "plain text\n"
