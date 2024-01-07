import base64
import hashlib
import json
from typing import Any


def http_response(body: dict[str, Any], status: int = 200) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def http_error(
    message: str = "Internal server error", status: int = 500
) -> dict[str, Any]:
    return http_response({"message": message}, status=status)


def shorten(url: str, length=10) -> str:
    # Hash the URL using SHA256
    hash_object = hashlib.sha256(url.encode())
    hash_digest = hash_object.digest()

    # Encode the hash in base64
    base64_encoded = base64.urlsafe_b64encode(hash_digest)

    # Truncate and return the result
    return base64_encoded[:length].decode()


def event_field(event: dict[str, Any], field: str, required: bool = False):
    if required and field not in event:
        raise ValueError(f"field '{field}' cannot be missing")
    return event[field]
