import json

from urlup_be.lambdas.handlers.package.redirect import (
    handler as redirect_handler,
)
from urlup_be.lambdas.handlers.package.shorten import (
    handler as shorten_handler,
)
from urlup_be.lambdas.handlers.package.util import encode_body, shorten

from .fixtures import dynamodb, dynamodb_table  # pylint: disable=unused-import


def test_flow(dynamodb, dynamodb_table):
    input_url = "https://example.com"
    shortcode = shorten(input_url)

    # test that the key isn't in the table
    response = dynamodb_table.get_item(Key={"short": shortcode})
    assert "Item" not in response

    shorten_event = {"body": encode_body({"url": input_url})}

    # Test initial shortening
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
    }

    response = dynamodb_table.get_item(Key={"short": shortcode})
    assert "Item" in response

    # Test redirect
    redirect_event = {"body": encode_body({"shortcode": shortcode})}
    response = redirect_handler(redirect_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
    }


def test_duplicate(dynamodb, dynamodb_table):
    input_url = "https://example.com"
    shortcode = shorten(input_url)

    shorten_event = {"body": encode_body({"url": input_url})}

    # Test initial shortening
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
    }

    # Test duplicate request
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
    }

    # Test duplicate request, but with a trailing slash
    shorten_event = {"body": encode_body({"url": f"{input_url}/"})}
    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": shortcode,
    }
