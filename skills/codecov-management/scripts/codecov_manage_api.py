from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib import error, parse, request

from codecov_manage_common import CodecovCliError, join_message

if TYPE_CHECKING:
    from collections.abc import Iterable

JsonObject = dict[str, Any]

DEFAULT_BASE_URL = "https://api.codecov.io"
DEFAULT_SERVICE = "github"
DEFAULT_TOKEN_ENVS = ("CODECOV_TOKEN", "CODECOV_API_TOKEN")
UNTRUSTED_API_TEXT_MAX_LENGTH = 500
REMOTE_SECTION = re.compile(r'^\s*\[remote "([^"]+)"\]\s*$')
MIN_REMOTE_PATH_PARTS = 2


@dataclass(frozen=True)
class CodecovContext:
    repo_root: Path
    service: str
    owner: str
    repo_name: str
    base_url: str
    token: str | None
    token_env_name: str | None
    codecov_yml_path: Path | None


@dataclass(frozen=True)
class RequestSpec:
    method: str
    endpoint: str
    query: dict[str, str] | None = None
    form: dict[str, str] | None = None
    json_body: JsonObject | None = None


@dataclass(frozen=True)
class RemoteSlug:
    service: str
    owner: str
    repo_name: str


def resolve_context(args: Any) -> CodecovContext:
    repo_root = resolve_repo_root(Path(args.repo))
    remote_slug = resolve_remote_slug(repo_root)

    service = normalize_service(args.service or remote_slug.service if remote_slug else DEFAULT_SERVICE)
    owner = args.owner or (remote_slug.owner if remote_slug else None)
    repo_name = args.repo_name or (remote_slug.repo_name if remote_slug else None)
    if not owner or not repo_name:
        raise CodecovCliError(
            join_message(
                "Could not resolve a Codecov repository slug.",
                "Provide --owner and --repo-name, or run from a checkout with a GitHub/GitLab/Bitbucket origin remote.",
            )
        )

    token, token_env_name = resolve_token(
        args.token_envs or list(DEFAULT_TOKEN_ENVS),
        required=not args.allow_unauthenticated,
    )

    codecov_yml_path = find_codecov_yml(repo_root)
    return CodecovContext(
        repo_root=repo_root,
        service=service,
        owner=owner,
        repo_name=repo_name,
        base_url=sanitize_base_url(args.base_url),
        token=token,
        token_env_name=token_env_name,
        codecov_yml_path=codecov_yml_path,
    )


def resolve_repo_root(start: Path) -> Path:
    candidate = start.resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for parent in (candidate, *candidate.parents):
        if (parent / ".git").exists() or find_codecov_yml(parent) is not None:
            return parent

    return candidate


def find_codecov_yml(repo_root: Path) -> Path | None:
    for filename in ("codecov.yml", ".codecov.yml", "codecov.yaml", ".codecov.yaml"):
        candidate = repo_root / filename
        if candidate.is_file():
            return candidate
    return None


def sanitize_base_url(value: str | None) -> str:
    base_url = (value or DEFAULT_BASE_URL).strip()
    if not base_url:
        return DEFAULT_BASE_URL

    parsed = parse.urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CodecovCliError(f"Codecov base URL must be an absolute HTTPS URL: {base_url}")

    return base_url.rstrip("/")


def normalize_service(value: str) -> str:
    service = value.strip().lower()
    aliases = {
        "gh": "github",
        "github.com": "github",
        "gitlab.com": "gitlab",
        "bitbucket.org": "bitbucket",
    }
    return aliases.get(service, service)


def resolve_token(token_envs: Iterable[str], *, required: bool) -> tuple[str | None, str | None]:
    checked_names: list[str] = []
    for raw_name in token_envs:
        name = raw_name.strip()
        if not name:
            continue

        checked_names.append(name)
        token = os.getenv(name)
        if token:
            return token, name

    if not required:
        return None, None

    env_list = ", ".join(checked_names or list(DEFAULT_TOKEN_ENVS))
    raise CodecovCliError(f"No Codecov token was found in the configured environment variables: {env_list}.")


def resolve_remote_slug(repo_root: Path) -> RemoteSlug | None:
    remote_url = read_origin_remote_url(repo_root)
    if remote_url is None:
        return None
    return parse_remote_slug(remote_url)


def read_origin_remote_url(repo_root: Path) -> str | None:
    git_dir = resolve_git_dir(repo_root)
    if git_dir is None:
        return None

    config_path = git_dir / "config"
    if not config_path.is_file():
        return None

    current_remote: str | None = None
    for raw_line in config_path.read_text(encoding="utf8").splitlines():
        section_match = REMOTE_SECTION.match(raw_line)
        if section_match:
            current_remote = section_match.group(1)
            continue

        if current_remote != "origin":
            continue

        key, separator, value = raw_line.strip().partition("=")
        if separator and key.strip() == "url":
            return value.strip()

    return None


def resolve_git_dir(repo_root: Path) -> Path | None:
    git_entry = repo_root / ".git"
    if git_entry.is_dir():
        return git_entry
    if not git_entry.is_file():
        return None

    raw_value = git_entry.read_text(encoding="utf8").strip()
    prefix = "gitdir:"
    if not raw_value.lower().startswith(prefix):
        return None

    gitdir_value = raw_value[len(prefix) :].strip()
    gitdir_path = Path(gitdir_value)
    if gitdir_path.is_absolute():
        return gitdir_path
    return (repo_root / gitdir_path).resolve()


def parse_remote_slug(remote_url: str) -> RemoteSlug | None:
    normalized = remote_url.strip().removesuffix(".git")

    scp_like = re.match(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)$", normalized)
    if scp_like:
        return slug_from_host_and_path(scp_like.group("host"), scp_like.group("path"))

    parsed = parse.urlsplit(normalized)
    if parsed.scheme and parsed.netloc:
        return slug_from_host_and_path(parsed.netloc, parsed.path.lstrip("/"))

    return None


def slug_from_host_and_path(host: str, path_value: str) -> RemoteSlug | None:
    parts = [part for part in path_value.strip("/").split("/") if part]
    if len(parts) < MIN_REMOTE_PATH_PARTS:
        return None

    service = service_from_host(host)
    if service is None:
        return None

    return RemoteSlug(service=service, owner=parts[-2], repo_name=parts[-1])


def service_from_host(host: str) -> str | None:
    normalized = host.lower()
    if normalized.endswith("github.com"):
        return "github"
    if normalized.endswith("gitlab.com"):
        return "gitlab"
    if normalized.endswith("bitbucket.org"):
        return "bitbucket"
    return None


def repo_api_endpoint(context: CodecovContext, suffix: str = "") -> str:
    cleaned_suffix = suffix.lstrip("/")
    base = (
        f"/api/v2/{parse.quote(context.service)}/{parse.quote(context.owner)}/repos/{parse.quote(context.repo_name)}/"
    )
    return f"{base}{cleaned_suffix}"


def api_request(*, context: CodecovContext, spec: RequestSpec) -> Any:
    url = build_url(context.base_url, spec.endpoint, spec.query)
    headers = {"Accept": "application/json"}
    if context.token is not None:
        headers["Authorization"] = f"Bearer {context.token}"

    data: bytes | None = None
    if spec.form is not None:
        data = parse.urlencode(spec.form).encode("utf8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif spec.json_body is not None:
        data = json.dumps(spec.json_body).encode("utf8")
        headers["Content-Type"] = "application/json"

    request_object = request.Request(  # noqa: S310 - URL is constrained by build_url.
        url=url,
        data=data,
        headers=headers,
        method=spec.method,
    )

    try:
        with request.urlopen(request_object) as response:  # noqa: S310 - request_object uses the validated URL above.
            raw_body = response.read()
    except error.HTTPError as http_error:
        detail = read_error_body(http_error)
        raise CodecovCliError(
            f"Codecov API {spec.method} {spec.endpoint} failed with HTTP {http_error.code}: {detail}"
        ) from http_error
    except error.URLError as url_error:
        raise CodecovCliError(f"Failed to reach Codecov at {context.base_url}: {url_error.reason}") from url_error

    if not raw_body:
        return None

    decoded = raw_body.decode("utf8", errors="replace")
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return decoded


def build_url(base_url: str, endpoint: str, query: dict[str, str] | None) -> str:
    if parse.urlsplit(endpoint).scheme:
        url = validate_absolute_endpoint(base_url, endpoint)
    else:
        if not endpoint.startswith("/"):
            raise CodecovCliError(f"Endpoint must start with '/': {endpoint}")
        url = f"{base_url}{endpoint}"

    if not query:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{parse.urlencode(query)}"


def validate_absolute_endpoint(base_url: str, endpoint: str) -> str:
    base_parts = parse.urlsplit(base_url)
    endpoint_parts = parse.urlsplit(endpoint)

    if endpoint_parts.scheme != "https" or not endpoint_parts.netloc:
        raise CodecovCliError(f"Absolute endpoint must be an HTTPS URL: {endpoint}")

    if (
        endpoint_parts.scheme.lower(),
        endpoint_parts.netloc.lower(),
    ) != (
        base_parts.scheme.lower(),
        base_parts.netloc.lower(),
    ):
        raise CodecovCliError(
            join_message(
                "Absolute endpoint host must match the configured Codecov base URL.",
                "Set --base-url to the intended Codecov origin and pass a relative endpoint path.",
            )
        )

    return endpoint


def read_error_body(http_error: error.HTTPError) -> str:
    try:
        raw_body = http_error.read().decode("utf8", errors="replace").strip()
    except OSError:  # pragma: no cover
        raw_body = ""

    if raw_body:
        return mark_untrusted_api_text(raw_body)

    return mark_untrusted_api_text(http_error.reason or "no additional error details")


def mark_untrusted_api_text(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) > UNTRUSTED_API_TEXT_MAX_LENGTH:
        cleaned = f"{cleaned[:UNTRUSTED_API_TEXT_MAX_LENGTH].rstrip()} ... [truncated]"
    return f"[untrusted-codecov-text] {cleaned}"


def require_json_object(payload: Any, error_message: str) -> JsonObject:
    if not isinstance(payload, dict):
        raise CodecovCliError(error_message)

    return cast("JsonObject", payload)
