import os
from typing import Any

import pytest

from urlup_be.lambdas.handlers.package import util


@pytest.mark.parametrize(
    "allowed_origin,origin,matches",
    [
        ("https://example.com", "http://example.com", False),
        ("https://example.com", "https://example.com", True),
        ("re:http.*://example\\.com", "https://example.com", True),
        ("re:https?://example\\.com", "https://www.example.com", False),
        ("re:https://.*example\\.com", "https://example.com", True),
        ("re:https://.*example\\.com", "https://www.example.com", True),
        ("re:https://.*example\\.com", "http://www.example.com", False),
        ("re:http.*://.*example\\.com", "https://www.example.com", True),
        ("re:http.*://.*example\\.com", "http://example.com", True),
    ],
)
def test_origin_matches(allowed_origin: str, origin: str, matches: bool):
    assert util.origin_matches(allowed_origin, origin) == matches


@pytest.mark.parametrize(
    "origin,allowed_frontends,allowed_origin",
    [
        ("", ["https://example.com"], None),
        ("https://example.com", [], None),
        ("https://example.com", None, None),
        ("https://example.com", ["https://example.net"], None),
        (
            "https://example.com",
            ["https://example.net", "https://example.com"],
            "https://example.com",
        ),
        (
            "https://example.net",
            ["https://example.net", "https://example.com"],
            "https://example.net",
        ),
        (
            "https://example.net",
            ["https://example.(net|com)", "https://example.com"],
            None,
        ),
        (
            "https://example.net",
            ["re:https://example\\.(net|com)", "https://example.com"],
            "https://example.net",
        ),
    ],
)
def test_get_allowed_origin(
    origin: str,
    allowed_frontends: list[str] | None,
    allowed_origin: str | None,
):
    os.environ.pop("ALLOWED_FRONTENDS", "")
    # Test with an explicit set of allowed_frontends
    assert (
        util.get_allowed_origin(origin, allowed_frontends=allowed_frontends)
        == allowed_origin
    )

    # Test without any allowed frontends
    assert util.get_allowed_origin(origin) is None

    # Test with the environment variable
    if allowed_frontends is not None:
        os.environ["ALLOWED_FRONTENDS"] = util.URL_DELIMITER.join(
            allowed_frontends
        )
    assert util.get_allowed_origin(origin) == allowed_origin


@pytest.mark.parametrize(
    "test_body",
    [
        ({"Arbitrar": "keys", "and": ["val", "ues"]}),
        ({"1234": 32145, "and": {"val": "ues"}}),
    ],
)
def test_en_de_code(test_body: dict[str, Any]):
    encoded = util.encode_body(test_body)
    assert isinstance(encoded, str)
    assert test_body == util.decode_body(encoded)
