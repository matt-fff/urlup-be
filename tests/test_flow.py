import json

from urlup_be.lambdas.redirect.handler import handler as redirect_handler
from urlup_be.lambdas.shorten.handler import handler as shorten_handler
from urlup_be.lambdas.shorten.handler import shorten

from .fixtures import dynamodb, dynamodb_table  # pylint: disable=unused-import


def test_flow(dynamodb, dynamodb_table):
    input_url = "https://example.com"
    short_url = shorten(input_url)

    # test that the key isn't in the table
    response = dynamodb_table.get_item(Key={"short": short_url})
    assert "Item" not in response

    shorten_event = {"body": json.dumps({"url": input_url})}

    response = shorten_handler(shorten_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": short_url,
    }

    response = dynamodb_table.get_item(Key={"short": short_url})
    assert "Item" in response

    redirect_event = {"body": json.dumps({"url": short_url})}
    response = redirect_handler(redirect_event, {})
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "url": input_url,
        "short": short_url,
    }
