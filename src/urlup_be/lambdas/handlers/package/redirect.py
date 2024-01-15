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
    query_params = event.get("pathParameters", {})
    log = LOG.bind(lambda_event=event, context=context, ddb_table=ddb_table)

    try:
        # shortcode = util.event_field(event, "shortcode", required=True)
        shortcode = query_params["shortcode"]
    except (KeyError, ValueError) as exc:
        log.warn("missing_field", exc=exc)
        return util.http_error(message=" - ".join(exc.args), status=400)

    ddb_key = {"short": {"S": shortcode}}

    # Check if the URL is in DynamoDB
    try:
        response = ddb_client.update_item(
            TableName=ddb_table,
            Key=ddb_key,
            UpdateExpression="SET clicks = clicks + :val",
            ExpressionAttributeValues={":val": {"N": "1"}},
            ReturnValues="ALL_NEW",
        )
    except ClientError:
        return util.http_error(message="URL not found", status=404)
    except Exception:
        log.exception("ddb_update_failure")
        return util.http_error()

    if "Attributes" not in response:
        return util.http_error(message="URL not found", status=404)

    output_url = response["Attributes"]["url"]["S"]

    return {
        "statusCode": 302,
        "headers": {"Location": output_url},
        "body": "Redirecting...",
    }
