from __future__ import annotations

import io
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self
from urllib import error, request

import codecov_manage_api
import pytest
from codecov_manage_common import CodecovCliError


def test_absolute_endpoint_must_match_base_url_origin() -> None:
    with pytest.raises(CodecovCliError, match="Absolute endpoint host must match"):
        _ = codecov_manage_api.build_url(
            "https://api.codecov.io",
            "https://example.invalid/api/v2/github/owner/repos/repo/",
            None,
        )


def test_absolute_endpoint_must_use_https() -> None:
    insecure_endpoint = "http" + "://api.codecov.io/api/v2/github/owner/repos/repo/"

    with pytest.raises(CodecovCliError, match="HTTPS"):
        _ = codecov_manage_api.build_url(
            "https://api.codecov.io",
            insecure_endpoint,
            None,
        )


def test_relative_endpoint_uses_configured_base_url() -> None:
    assert (
        codecov_manage_api.build_url(
            "https://api.codecov.io",
            "/api/v2/github/owner/repos/repo/",
            {"page_size": "10"},
        )
        == "https://api.codecov.io/api/v2/github/owner/repos/repo/?page_size=10"
    )


def test_parse_remote_slug_supports_github_ssh_and_https() -> None:
    assert codecov_manage_api.parse_remote_slug("git@github.com:Nick2bad4u/Codecov-Skill.git") == (
        codecov_manage_api.RemoteSlug(service="github", owner="Nick2bad4u", repo_name="Codecov-Skill")
    )
    assert codecov_manage_api.parse_remote_slug("https://gitlab.com/acme/example.git") == (
        codecov_manage_api.RemoteSlug(service="gitlab", owner="acme", repo_name="example")
    )


def test_resolve_repo_root_and_origin_remote_without_subprocess(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    nested = root / "packages" / "example"
    git_dir = root / ".git"
    nested.mkdir(parents=True)
    git_dir.mkdir()
    _ = (git_dir / "config").write_text(
        """
        [remote "origin"]
            url = git@github.com:Nick2bad4u/Codecov-Skill.git
        """,
        encoding="utf8",
    )

    assert codecov_manage_api.resolve_repo_root(nested) == root
    assert codecov_manage_api.resolve_remote_slug(root) == codecov_manage_api.RemoteSlug(
        service="github",
        owner="Nick2bad4u",
        repo_name="Codecov-Skill",
    )


def test_resolve_context_uses_remote_and_token_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    _ = (git_dir / "config").write_text(
        """
        [remote "origin"]
            url = https://github.com/Nick2bad4u/Codecov-Skill.git
        """,
        encoding="utf8",
    )
    monkeypatch.setenv("CODECOV_TOKEN_CUSTOM", "token-value")

    context = codecov_manage_api.resolve_context(
        SimpleNamespace(
            repo=str(tmp_path),
            service=None,
            owner=None,
            repo_name=None,
            base_url=None,
            token_envs=["CODECOV_TOKEN_CUSTOM"],
            allow_unauthenticated=False,
        )
    )

    assert context.service == "github"
    assert context.owner == "Nick2bad4u"
    assert context.repo_name == "Codecov-Skill"
    assert context.token == "token-value"


def test_resolve_token_can_allow_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODECOV_TOKEN", raising=False)
    assert codecov_manage_api.resolve_token(["CODECOV_TOKEN"], required=False) == (None, None)

    with pytest.raises(CodecovCliError, match="No Codecov token"):
        _ = codecov_manage_api.resolve_token(["CODECOV_TOKEN"], required=True)


def test_api_request_builds_bearer_json_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    captured: dict[str, Any] = {}

    def fake_urlopen(request_object: Any) -> Response:
        captured["url"] = request_object.full_url
        captured["headers"] = dict(request_object.header_items())
        captured["method"] = request_object.get_method()
        captured["data"] = request_object.data
        return Response()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    payload = codecov_manage_api.api_request(
        context=codecov_manage_api.CodecovContext(
            repo_root=tmp_path,
            service="github",
            owner="owner",
            repo_name="repo",
            base_url="https://api.codecov.io",
            token="token",
            token_env_name="CODECOV_TOKEN",
            codecov_yml_path=None,
        ),
        spec=codecov_manage_api.RequestSpec(
            method="POST",
            endpoint="/api/v2/github/owner/repos/repo/",
            query={"page_size": "1"},
            json_body={"name": "value"},
        ),
    )

    assert payload == {"ok": True}
    assert captured["url"] == "https://api.codecov.io/api/v2/github/owner/repos/repo/?page_size=1"
    assert captured["method"] == "POST"
    assert captured["data"] == b'{"name": "value"}'
    assert captured["headers"]["Authorization"] == "Bearer token"


def test_read_error_body_marks_http_details_untrusted() -> None:
    http_error = error.HTTPError(
        url="https://api.codecov.io/api/test",
        code=400,
        msg="Bad Request",
        hdrs=Message(),
        fp=io.BytesIO(b"external\nmessage"),
    )

    try:
        assert codecov_manage_api.read_error_body(http_error) == "[untrusted-codecov-text] external message"
    finally:
        http_error.close()
