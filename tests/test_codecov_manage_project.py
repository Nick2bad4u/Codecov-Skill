from __future__ import annotations

from pathlib import Path
from typing import Any, Self
from urllib import request

import codecov_manage_project
import pytest
from codecov_manage_api import CodecovContext


def make_context(tmp_path: Path, codecov_yml_path: Path | None = None) -> CodecovContext:
    return CodecovContext(
        repo_root=tmp_path,
        service="github",
        owner="Nick2bad4u",
        repo_name="Codecov-Skill",
        base_url="https://api.codecov.io",
        token="token",
        token_env_name="CODECOV_TOKEN",
        codecov_yml_path=codecov_yml_path,
    )


def test_repo_api_wrappers_build_expected_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, str] | None]] = []

    def fake_api_request(*, context: CodecovContext, spec: Any) -> dict[str, object]:
        del context
        calls.append((spec.method, spec.endpoint, spec.query))
        return {"results": []}

    monkeypatch.setattr(codecov_manage_project, "api_request", fake_api_request)
    context = make_context(tmp_path)

    codecov_manage_project.fetch_branches(context=context, page_size=10)
    codecov_manage_project.fetch_commits(context=context, branch="main", page_size=5)
    codecov_manage_project.fetch_file_report(context=context, commit="abc123", path="src/index.ts")

    assert calls == [
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/branches/", {"page_size": "10"}),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/commits/", {"page_size": "5", "branch": "main"}),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/commits/abc123/report/file/", {"path": "src/index.ts"}),
    ]


def test_more_repo_api_wrappers_build_expected_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, str] | None]] = []

    def fake_api_request(*, context: CodecovContext, spec: Any) -> dict[str, object]:
        del context
        calls.append((spec.method, spec.endpoint, spec.query))
        return {"results": []}

    monkeypatch.setattr(codecov_manage_project, "api_request", fake_api_request)
    context = make_context(tmp_path)

    codecov_manage_project.fetch_repo(context=context)
    codecov_manage_project.fetch_branch(context=context, branch="main")
    codecov_manage_project.fetch_commit(context=context, commit="abc123")
    codecov_manage_project.fetch_commit_report(context=context, commit="abc123")
    codecov_manage_project.fetch_report_tree(context=context, commit="abc123", path=None)
    codecov_manage_project.fetch_flags(context=context)
    codecov_manage_project.fetch_pulls(context=context, state="open", page_size=3)
    codecov_manage_project.fetch_pull(context=context, pull_id=42)
    codecov_manage_project.compare_commits(context=context, base="base", head="head")

    assert calls == [
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/branches/main/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/commits/abc123/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/commits/abc123/report/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/commits/abc123/report/tree/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/flags/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/pulls/", {"page_size": "3", "state": "open"}),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/pulls/42/", None),
        ("GET", "/api/v2/github/Nick2bad4u/repos/Codecov-Skill/compare/base...head/", None),
    ]


def test_build_summary_combines_api_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = make_context(tmp_path)

    def fake_fetch_repo(*, context: CodecovContext) -> dict[str, int]:
        assert context.repo_name == "Codecov-Skill"
        return {"coverage": 90}

    def fake_fetch_branches(*, context: CodecovContext, page_size: int) -> dict[str, list[dict[str, str]]]:
        assert context.service == "github"
        assert page_size == 1
        return {"results": [{"name": "main"}]}

    def fake_fetch_commits(
        *,
        context: CodecovContext,
        branch: str | None,
        page_size: int,
    ) -> dict[str, list[dict[str, str]]]:
        assert context.owner == "Nick2bad4u"
        assert branch == "main"
        assert page_size == 1
        return {"results": [{"commitid": "abc"}]}

    def fake_fetch_flags(*, context: CodecovContext) -> dict[str, list[dict[str, str]]]:
        assert context.token_env_name == "CODECOV_TOKEN"
        return {"results": [{"name": "python"}]}

    monkeypatch.setattr(codecov_manage_project, "fetch_repo", fake_fetch_repo)
    monkeypatch.setattr(codecov_manage_project, "fetch_branches", fake_fetch_branches)
    monkeypatch.setattr(codecov_manage_project, "fetch_commits", fake_fetch_commits)
    monkeypatch.setattr(codecov_manage_project, "fetch_flags", fake_fetch_flags)

    payload = codecov_manage_project.build_summary(context=context, branch="main", page_size=1)

    assert payload["repository"] == "Nick2bad4u/Codecov-Skill"
    assert payload["repo"] == {"coverage": 90}
    assert payload["branches"] == [{"name": "main"}]
    assert payload["commits"] == [{"commitid": "abc"}]
    assert payload["flags"] == [{"name": "python"}]


def test_direct_api_call_requires_no_network_when_dry_run(tmp_path: Path) -> None:
    assert (
        codecov_manage_project.direct_api_call(
            context=make_context(tmp_path),
            endpoint="/api/v2/github/owner/repos/repo/",
            method="POST",
            query={"a": "b"},
            form={"name": "value"},
            dry_run=True,
        )["dryRun"]
        is True
    )


def test_validate_config_posts_local_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"Valid!"

    config_path = tmp_path / "codecov.yml"
    _ = config_path.write_text("coverage: {}\n", encoding="utf8")
    captured: dict[str, object] = {}

    def fake_urlopen(request_object: Any) -> Response:
        captured["url"] = request_object.full_url
        captured["data"] = request_object.data
        return Response()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    payload = codecov_manage_project.validate_config(context=make_context(tmp_path, config_path))

    assert payload["valid"] is True
    assert payload["message"] == "Valid!"
    assert captured["url"] == "https://codecov.io/validate"
    assert captured["data"] == b"coverage: {}\n"


def test_build_config_template_includes_statuses_and_flag() -> None:
    template = codecov_manage_project.build_config_template(profile="python", flag="python", target=80)

    assert "target: 80%" in template
    assert "flags:" in template
    assert "- python" in template
    assert "tests/**" in template


def test_build_github_action_snippet_can_use_token() -> None:
    snippet = codecov_manage_project.build_github_action_snippet(
        flag="python",
        coverage_file="coverage/python.xml",
        test_results_file="test-report.junit.xml",
        use_oidc=False,
    )

    assert "token: ${{ secrets.CODECOV_TOKEN }}" in snippet
    assert "report_type: coverage" in snippet
    assert "report_type: test_results" in snippet
