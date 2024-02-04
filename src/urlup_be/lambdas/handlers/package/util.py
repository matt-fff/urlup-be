import base64
import hashlib
import json
import os
import re
from typing import Any, Optional

import structlog

URL_DELIMITER = "<<URL_DELIM>>"
REGEX_PREFIX = "re:"

LOG = structlog.get_logger()


def origin_matches(allowed_origin: str, origin: str) -> bool:
    if not allowed_origin:
        return False
    if not allowed_origin.startswith(REGEX_PREFIX):
        return allowed_origin == origin
    return bool(re.match(allowed_origin[len(REGEX_PREFIX) :], origin))


def get_allowed_frontends(
    allowed_frontends: list[str] | None = None,
) -> list[str]:
    if allowed_frontends is None:
        allowed_frontends = [
            fe
            for fe in os.environ.get("ALLOWED_FRONTENDS", "").split(
                URL_DELIMITER
            )
            if fe
        ]

    return allowed_frontends


def get_allowed_origin(
    origin: str, allowed_frontends: list[str] | None = None
) -> Optional[str]:
    allowed_frontends = get_allowed_frontends(
        allowed_frontends=allowed_frontends
    )

    if not allowed_frontends or not origin:
        return None

    for allowed_origin in allowed_frontends:
        if origin_matches(allowed_origin, origin):
            return origin
    return None


def add_allow_origin(headers: dict[str, Any], origin: str) -> Optional[str]:
    allowed_origin = get_allowed_origin(origin)
    if allowed_origin:
        headers["Access-Control-Allow-Origin"] = allowed_origin


def http_response(
    body: dict[str, Any], status: int = 200, origin: str = ""
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
    }

    add_allow_origin(headers, origin)

    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body),
    }


def http_error(
    message: str = "Internal server error", status: int = 500, origin: str = ""
) -> dict[str, Any]:
    return http_response({"message": message}, status=status, origin=origin)


def shorten(url: str, length=7) -> str:
    # Hash the URL using SHA256
    hash_object = hashlib.sha256(url.encode())
    hash_digest = hash_object.digest()

    # Encode the hash in base64
    base64_encoded = base64.urlsafe_b64encode(hash_digest)

    # Truncate and return the result
    return base64_encoded[:length].decode()


def decode_body(b64_body: str) -> dict[str, Any]:
    return json.loads(base64.b64decode(b64_body.encode()).decode())


def encode_body(body: dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(body).encode()).decode()


def event_field(event: dict[str, Any], field: str, required: bool = False):
    if "body" not in event:
        raise ValueError("request body cannot be missing")

    body = decode_body(event["body"])
    if required and field not in body:
        raise ValueError(f"field '{field}' cannot be missing")
    return body[field]
