from __future__ import annotations

import pytest
from codecov_manage_common import CodecovCliError, parse_name_value_pairs, require_positive_integer, resolve_csv_values


def test_parse_name_value_pairs() -> None:
    assert parse_name_value_pairs(["page=1", "state=open"], argument_name="query-param") == {
        "page": "1",
        "state": "open",
    }


def test_parse_name_value_pairs_rejects_missing_separator() -> None:
    with pytest.raises(CodecovCliError, match="key=value"):
        _ = parse_name_value_pairs(["page"], argument_name="query-param")


def test_resolve_csv_values() -> None:
    assert resolve_csv_values(["python, javascript", "docs"], argument_name="flag") == [
        "python",
        "javascript",
        "docs",
    ]


def test_require_positive_integer() -> None:
    assert require_positive_integer(1, argument_name="page-size") == 1
    with pytest.raises(CodecovCliError, match="at least 1"):
        _ = require_positive_integer(0, argument_name="page-size")
