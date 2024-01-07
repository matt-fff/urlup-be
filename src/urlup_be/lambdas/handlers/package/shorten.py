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
        input_url = util.event_field(event, "url", required=True).rstrip("/?")
    except ValueError as exc:
        log.warn("missing_field", exc=exc)
        return util.http_error(message=" - ".join(exc.args), status=400)

    shortened = util.shorten(input_url)

    # Check if the URL is in DynamoDB
    try:
        response = ddb_client.get_item(
            TableName=ddb_table, Key={"short": {"S": shortened}}
        )
    except Exception:
        log.exception()
        return util.http_error()

    if "Item" in response:
        # URL found in DynamoDB
        stored_url = response["Item"]["url"]["S"]

        # NOTE duplicate consolidation isn't standard behavior.
        # If individual user metrics are introduced,
        # even duplicates need separate records.
        if stored_url != input_url:
            log.error("collision_detected", ddb_response=response)
            return util.http_error()
    else:
        ddb_client.put_item(
            TableName=ddb_table,
            Item={"url": {"S": input_url}, "short": {"S": shortened}},
        )

    return util.http_response(
        {"url": input_url, "short": shortened}, status=200
    )
