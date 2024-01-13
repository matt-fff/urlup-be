import os
from datetime import datetime, timezone

import boto3
import structlog
from botocore.exceptions import ClientError

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

    clicks = 0
    shortened = util.shorten(input_url)
    ddb_key = {"short": {"S": shortened}}
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        response = ddb_client.update_item(
            TableName=ddb_table,
            Key=ddb_key,
            ExpressionAttributeValues={
                ":url": {"S": input_url},
                ":created_at": {"S": created_at},
                ":clicks": {"N": str(clicks)},
            },
            UpdateExpression="""
                SET #url = :url,
                created_at = :created_at,
                clicks = :clicks
            """,
            ExpressionAttributeNames={"#short": "short", "#url": "url"},
            ConditionExpression="attribute_not_exists(#short)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            log.exception("ddb_update_failure")
            return util.http_error()

        response = ddb_client.get_item(TableName=ddb_table, Key=ddb_key)
    except Exception:
        log.exception("ddb_update_failure")
        return util.http_error()

    if "Item" in response:
        # URL found in DynamoDB
        stored_url = response["Item"]["url"]["S"]
        clicks = response["Item"]["clicks"]["N"]
        created_at = response["Item"]["created_at"]["S"]

        # NOTE duplicate consolidation isn't standard behavior.
        # If individual user metrics are introduced,
        # even duplicates need separate records.
        if stored_url != input_url:
            log.error("collision_detected", ddb_response=response)
            # TODO have a graceful way to make the shortcode unique
            return util.http_error()

    return util.http_response(
        {
            "url": input_url,
            "short": shortened,
            "clicks": int(clicks),
            "created_at": created_at,
        },
        status=200,
    )
