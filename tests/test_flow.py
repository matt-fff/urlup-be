import json
from datetime import datetime, timezone
from typing import Any

from freezegun import freeze_time

from urlup_be.lambdas.handlers.package.get import handler as get_handler
from urlup_be.lambdas.handlers.package.redirect import (
    handler as redirect_handler,
)
from urlup_be.lambdas.handlers.package.shorten import (
    handler as shorten_handler,
)
from urlup_be.lambdas.handlers.package.util import encode_body, shorten

from .fixtures import dynamodb, dynamodb_table  # pylint: disable=unused-import


def event_body(**kwargs) -> dict[str, Any]:
    return {"body": encode_body(kwargs)}


def event_qparams(**kwargs) -> dict[str, Any]:
    return {"pathParameters": kwargs}


def test_flow(dynamodb, dynamodb_table):
    input_url = "https://example.com"
    shortcode = shorten(input_url)

    # test that the key isn't in the table
    response = dynamodb_table.get_item(Key={"short": shortcode})
    assert "Item" not in response

    # test a redirect 404
    response = redirect_handler(event_qparams(shortcode=shortcode), {})
    assert response["statusCode"] == 404

    # test a get 404
    response = get_handler(event_body(shortcode=shortcode), {})
    assert response["statusCode"] == 404

    now = datetime.now(timezone.utc)
    with freeze_time(now):
        # Test initial shortening
        response = shorten_handler(event_body(url=input_url), {})

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 0,
        "created_at": now.isoformat(),
    }

    response = dynamodb_table.get_item(Key={"short": shortcode})
    assert "Item" in response

    # Test get
    response = get_handler(event_body(shortcode=shortcode), {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 0,
        "created_at": now.isoformat(),
    }

    # Test redirect
    response = redirect_handler(event_qparams(shortcode=shortcode), {})
    assert response["statusCode"] == 302
    assert response["headers"]["Location"] == input_url

    # Test get
    response = get_handler(event_body(shortcode=shortcode), {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 1,
        "created_at": now.isoformat(),
    }


def test_duplicate(dynamodb, dynamodb_table):
    input_url = "https://example.com"
    shortcode = shorten(input_url)

    shorten_event = {"body": encode_body({"url": input_url})}

    now = datetime.now(timezone.utc)
    with freeze_time(now):
        # Test initial shortening
        response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 0,
        "created_at": now.isoformat(),
    }

    # Test duplicate request
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 0,
        "created_at": now.isoformat(),
    }

    # Test duplicate request, but with a trailing slash
    shorten_event = {"body": encode_body({"url": f"{input_url}/"})}
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
        "clicks": 0,
        "created_at": now.isoformat(),
    }
