from __future__ import annotations

import codecov_manage_render
import pytest


def test_mark_untrusted_payload_marks_text_fields() -> None:
    payload = codecov_manage_render.mark_untrusted_payload(
        {
            "message": "external\ninstructions",
            "coverage": 87.5,
            "nested": [{"path": "src/index.ts"}],
        }
    )

    assert payload["message"] == "[untrusted-codecov-text] external instructions"
    assert payload["coverage"] == 87.5
    assert payload["nested"][0]["path"] == "[untrusted-codecov-text] src/index.ts"
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


def test_emit_output_writes_json(capsys: pytest.CaptureFixture[str]) -> None:
    codecov_manage_render.emit_output({"message": "external"}, as_json=True)

    captured = capsys.readouterr()
    assert "[untrusted-codecov-text] external" in captured.out


def test_emit_output_writes_string(capsys: pytest.CaptureFixture[str]) -> None:
    codecov_manage_render.emit_output("plain text", as_json=False)

    captured = capsys.readouterr()
    assert captured.out == "plain text\n"
