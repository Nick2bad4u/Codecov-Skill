from __future__ import annotations

import argparse
from pathlib import Path

import manage_codecov
import pytest
from codecov_manage_api import CodecovContext
from codecov_manage_common import CodecovCliError


def make_context(tmp_path: Path) -> CodecovContext:
    return CodecovContext(
        repo_root=tmp_path,
        service="github",
        owner="Nick2bad4u",
        repo_name="Codecov-Skill",
        base_url="https://api.codecov.io",
        token="token",
        token_env_name="CODECOV_TOKEN",
        codecov_yml_path=None,
    )


def test_parse_args_builds_command_table_and_normalizes_global_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_codecov.py",
            "commits",
            "--page-size",
            "10",
            "--repo",
            ".",
            "--json",
            "--allow-unauthenticated",
        ],
    )

    args = manage_codecov.parse_args()

    assert args.command == "commits"
    assert args.repo == "."
    assert args.json is True
    assert args.allow_unauthenticated is True
    assert args.page_size == 10


def test_normalize_global_args_requires_values() -> None:
    with pytest.raises(CodecovCliError, match="Missing value"):
        _ = manage_codecov.normalize_global_args(["summary", "--repo"])


def test_dispatch_command_prints_config_without_context_api(tmp_path: Path) -> None:
    args = argparse.Namespace(command="print-config", profile="python", flag=None, target=75)

    output = manage_codecov.dispatch_command(args, make_context(tmp_path))

    assert isinstance(output, str)
    assert "coverage:" in output
    assert "- python" in output


def test_non_get_api_call_requires_dry_run(tmp_path: Path) -> None:
    args = argparse.Namespace(
        command="api-call",
        endpoint="/api/v2/github/owner/repos/repo/",
        method="POST",
        query_params=None,
        form_params=None,
        dry_run=False,
    )

    with pytest.raises(CodecovCliError, match="Non-GET"):
        manage_codecov.dispatch_command(args, make_context(tmp_path))


def test_dispatch_command_rejects_unknown_command(tmp_path: Path) -> None:
    args = argparse.Namespace(command="unknown")

    with pytest.raises(CodecovCliError, match="Unsupported command"):
        manage_codecov.dispatch_command(args, make_context(tmp_path))
