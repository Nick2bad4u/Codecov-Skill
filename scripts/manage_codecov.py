#!/usr/bin/env python3
# pyright: reportUnusedCallResult=false
"""Inspect and manage Codecov repository coverage resources."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from codecov_manage_api import DEFAULT_BASE_URL, DEFAULT_SERVICE, resolve_context
from codecov_manage_common import CodecovCliError, parse_name_value_pairs, require_positive_integer
from codecov_manage_project import (
    DEFAULT_PAGE_SIZE,
    build_config_template,
    build_github_action_snippet,
    build_summary,
    compare_commits,
    direct_api_call,
    fetch_branch,
    fetch_branches,
    fetch_commit,
    fetch_commit_report,
    fetch_commits,
    fetch_file_report,
    fetch_flags,
    fetch_pull,
    fetch_pulls,
    fetch_repo,
    fetch_report_tree,
    validate_config,
)
from codecov_manage_render import emit_output

if TYPE_CHECKING:
    from collections.abc import Callable

    from codecov_manage_api import CodecovContext

HELP_COMMIT = "Commit SHA or Codecov commit id."
HELP_PAGE_SIZE = "Maximum number of results to request."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Codecov repository coverage and configuration using environment-variable tokens.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--repo", default=".", help="Path inside the target repository checkout.")
    parser.add_argument(
        "--service", default=None, help=f"Codecov service slug. Defaults to remote detection or {DEFAULT_SERVICE}."
    )
    parser.add_argument("--owner", default=None, help="Repository owner or organization.")
    parser.add_argument("--repo-name", default=None, help="Repository name.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Codecov API base URL.")
    parser.add_argument(
        "--token-env",
        action="append",
        dest="token_envs",
        default=None,
        help="Environment variable name that may contain a Codecov token. Repeat to provide fallbacks.",
    )
    parser.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help="Allow API requests without a Codecov token for public endpoints.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text output.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary", help="Fetch repository, branch, commit, and flag summary data.")
    summary_parser.add_argument("--branch", default=None, help="Optional branch filter for commits.")
    add_page_size_arg(summary_parser)

    subparsers.add_parser("repo", help="Fetch repository metadata.")

    branches_parser = subparsers.add_parser("branches", help="List repository branches.")
    add_page_size_arg(branches_parser)

    branch_parser = subparsers.add_parser("branch", help="Fetch one branch.")
    branch_parser.add_argument("--branch", required=True, help="Branch name.")

    commits_parser = subparsers.add_parser("commits", help="List repository commits.")
    commits_parser.add_argument("--branch", default=None, help="Optional branch filter.")
    add_page_size_arg(commits_parser)

    commit_parser = subparsers.add_parser("commit", help="Fetch one commit.")
    commit_parser.add_argument("--commit", required=True, help=HELP_COMMIT)

    commit_report_parser = subparsers.add_parser("commit-report", help="Fetch report totals for one commit.")
    commit_report_parser.add_argument("--commit", required=True, help=HELP_COMMIT)

    report_tree_parser = subparsers.add_parser("report-tree", help="Fetch report tree data for one commit.")
    report_tree_parser.add_argument("--commit", required=True, help=HELP_COMMIT)
    report_tree_parser.add_argument("--path", default=None, help="Optional report tree path.")

    file_report_parser = subparsers.add_parser("file-report", help="Fetch coverage details for one file in a commit.")
    file_report_parser.add_argument("--commit", required=True, help=HELP_COMMIT)
    file_report_parser.add_argument("--path", required=True, help="File path in the Codecov report.")

    subparsers.add_parser("flags", help="List repository flags.")

    pulls_parser = subparsers.add_parser("pulls", help="List pull requests known to Codecov.")
    pulls_parser.add_argument("--state", default=None, help="Optional pull request state filter.")
    add_page_size_arg(pulls_parser)

    pull_parser = subparsers.add_parser("pull", help="Fetch one pull request by id.")
    pull_parser.add_argument("--pull-id", type=int, required=True, help="Pull request number.")

    compare_parser = subparsers.add_parser("compare", help="Compare two commits.")
    compare_parser.add_argument("--base", required=True, help="Base commit SHA.")
    compare_parser.add_argument("--head", required=True, help="Head commit SHA.")

    validate_parser = subparsers.add_parser("validate-config", help="Validate a local codecov.yml file.")
    validate_parser.add_argument("--config", default=None, help="Optional explicit codecov.yml path.")

    print_config_parser = subparsers.add_parser("print-config", help="Print a starter codecov.yml template.")
    print_config_parser.add_argument(
        "--profile", choices=("python", "node", "javascript", "typescript", "generic"), default="python"
    )
    print_config_parser.add_argument("--flag", default=None, help="Coverage flag to include.")
    print_config_parser.add_argument(
        "--target", type=int, default=75, help="Project and patch coverage target percentage."
    )

    action_parser = subparsers.add_parser(
        "github-action-snippet", help="Print a Codecov GitHub Actions upload snippet."
    )
    action_parser.add_argument("--flag", default="python", help="Codecov flag to upload.")
    action_parser.add_argument("--coverage-file", default="coverage/python.xml", help="Coverage report path.")
    action_parser.add_argument("--test-results-file", default=None, help="Optional test-results report path.")
    action_parser.add_argument("--use-token", action="store_true", help="Use secrets.CODECOV_TOKEN instead of OIDC.")

    api_call_parser = subparsers.add_parser("api-call", help="Call a Codecov API endpoint directly as an escape hatch.")
    api_call_parser.add_argument(
        "--endpoint", required=True, help="API endpoint path. Absolute URLs must match --base-url."
    )
    api_call_parser.add_argument(
        "--method", choices=("GET", "POST", "PATCH", "PUT", "DELETE"), default="GET", help="HTTP method."
    )
    api_call_parser.add_argument(
        "--query-param",
        action="append",
        dest="query_params",
        default=None,
        help="Query parameter in key=value form. Repeat as needed.",
    )
    api_call_parser.add_argument(
        "--form-param",
        action="append",
        dest="form_params",
        default=None,
        help="Form parameter in key=value form. Repeat as needed.",
    )
    api_call_parser.add_argument(
        "--dry-run", action="store_true", help="Print the intended request without sending it."
    )

    return parser.parse_args(normalize_global_args(sys.argv[1:]))


def add_page_size_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help=HELP_PAGE_SIZE)


def normalize_global_args(argv: list[str]) -> list[str]:
    flags_with_values = {
        "--repo",
        "--service",
        "--owner",
        "--repo-name",
        "--base-url",
        "--token-env",
    }
    flags_without_values = {"--json", "--allow-unauthenticated"}

    global_args: list[str] = []
    other_args: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]

        if argument in flags_without_values:
            global_args.append(argument)
            index += 1
            continue

        if argument in flags_with_values:
            next_index = index + 1
            if next_index >= len(argv):
                raise CodecovCliError(f"Missing value for global argument: {argument}")

            global_args.extend((argument, argv[next_index]))
            index += 2
            continue

        other_args.append(argument)
        index += 1

    return [*global_args, *other_args]


def main() -> int:
    try:
        args = parse_args()
        context = resolve_context(args)
        payload = dispatch_command(args, context)
        emit_output(payload, as_json=args.json)
    except CodecovCliError as error_message:
        sys.stderr.write(f"Error: {error_message}\n")
        return 1
    return 0


def dispatch_command(args: argparse.Namespace, context: CodecovContext) -> Any:
    handlers: dict[str, Callable[[], Any]] = {
        "summary": lambda: build_summary(
            context=context,
            branch=args.branch,
            page_size=require_positive_integer(args.page_size, argument_name="page-size"),
        ),
        "repo": lambda: fetch_repo(context=context),
        "branches": lambda: fetch_branches(
            context=context,
            page_size=require_positive_integer(args.page_size, argument_name="page-size"),
        ),
        "branch": lambda: fetch_branch(context=context, branch=args.branch),
        "commits": lambda: fetch_commits(
            context=context,
            branch=args.branch,
            page_size=require_positive_integer(args.page_size, argument_name="page-size"),
        ),
        "commit": lambda: fetch_commit(context=context, commit=args.commit),
        "commit-report": lambda: fetch_commit_report(context=context, commit=args.commit),
        "report-tree": lambda: fetch_report_tree(context=context, commit=args.commit, path=args.path),
        "file-report": lambda: fetch_file_report(context=context, commit=args.commit, path=args.path),
        "flags": lambda: fetch_flags(context=context),
        "pulls": lambda: fetch_pulls(
            context=context,
            state=args.state,
            page_size=require_positive_integer(args.page_size, argument_name="page-size"),
        ),
        "pull": lambda: fetch_pull(context=context, pull_id=args.pull_id),
        "compare": lambda: compare_commits(context=context, base=args.base, head=args.head),
        "validate-config": lambda: validate_config(
            context=context,
            config_path=Path(args.config) if args.config else None,
        ),
        "print-config": lambda: build_config_template(
            profile=args.profile,
            flag=args.flag or args.profile,
            target=args.target,
        ),
        "github-action-snippet": lambda: build_github_action_snippet(
            flag=args.flag,
            coverage_file=args.coverage_file,
            test_results_file=args.test_results_file,
            use_oidc=not args.use_token,
        ),
        "api-call": lambda: command_api_call(args, context),
    }

    try:
        return handlers[args.command]()
    except KeyError as error:
        raise CodecovCliError(f"Unsupported command: {args.command}") from error


def command_api_call(args: argparse.Namespace, context: CodecovContext) -> Any:
    if args.method != "GET" and not args.dry_run:
        raise CodecovCliError("Non-GET api-call requests must be reviewed with --dry-run first.")

    return direct_api_call(
        context=context,
        endpoint=args.endpoint,
        method=args.method,
        query=parse_name_value_pairs(args.query_params, argument_name="query-param"),
        form=parse_name_value_pairs(args.form_params, argument_name="form-param"),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
