import os

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
        shortcode = util.event_field(event, "shortcode", required=True)
    except ValueError as exc:
        log.warn("missing_field", exc=exc)
        return util.http_error(message=" - ".join(exc.args), status=400)

    ddb_key = {"short": {"S": shortcode}}

    # Check if the URL is in DynamoDB
    try:
        response = ddb_client.get_item(TableName=ddb_table, Key=ddb_key)
    except ClientError:
        return util.http_error(message="URL not found", status=404)
    except Exception:
        log.exception("ddb_update_failure")
        return util.http_error()

    if "Item" not in response:
        return util.http_error(message="URL not found", status=404)

    output_url = response["Item"]["url"]["S"]
    clicks = response["Item"]["clicks"]["N"]
    created_at = response["Item"]["created_at"]["S"]

    return util.http_response(
        {
            "url": output_url,
            "short": shortcode,
            "clicks": int(clicks),
            "created_at": created_at,
        },
        status=200,
    )
