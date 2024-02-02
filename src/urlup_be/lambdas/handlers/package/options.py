import structlog

from . import util

LOG = structlog.get_logger()


def handler(event, context):
    # NOTE I don't like having an explicit lambda for CORS.
    # Tried adding it as an x-amazon-apigateway-integration object,
    # but keep getting an "No integration defined for method" error
    # due to dependencies between routes.

    origin = event.get("headers", {}).get("Origin")
    headers = {
        "Access-Control-Allow-Methods": "OPTIONS,POST",
        "Access-Control-Allow-Headers": "Content-Type,X-Api-Key",
    }

    util.add_allow_origin(headers, origin)

    return {"statusCode": 200, "headers": headers}
