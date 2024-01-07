import os

import boto3
import structlog

from . import util

LOG = structlog.get_logger()


def handler(event, context):
    # Initialize DynamoDB client
    ddb_client = boto3.client("dynamodb")
    ddb_table = os.environ["DDB_TABLE"]
    log = LOG.bind(lambda_event=event, context=context, ddb_table=ddb_table)

    # Extract the URL from the event
    try:
        shortcode = util.event_field(event, "shortcode", required=True)
    except ValueError as exc:
        log.warn("missing_field", exc=exc)
        return util.http_error(message=" - ".join(exc.args), status=400)

    # Check if the URL is in DynamoDB
    try:
        response = ddb_client.get_item(
            TableName=ddb_table, Key={"short": {"S": shortcode}}
        )
    except Exception:
        log.exception()
        return util.http_error()

    if "Item" in response:
        # URL found in DynamoDB, return the value
        output_url = response["Item"]["url"]["S"]
    else:
        return util.http_error(message="URL not found", status=404)

    return util.http_response(
        {"url": output_url, "short": shortcode}, status=200
    )
