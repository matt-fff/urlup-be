import json

import boto3

from .config import Config

conf = Config()


def handler(event, context):
    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(conf.table_name)  # Replace with your table name

    # Extract the URL from the event
    input_url = json.loads(event["body"]).get("url", "")

    # Check if the URL is in DynamoDB
    try:
        response = table.get_item(Key={"short": input_url})
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Error accessing DynamoDB"}),
        }

    if "Item" in response:
        # URL found in DynamoDB, return the value
        output_url = response["Item"]["url"]
    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"message": "Failed to find URL"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"url": output_url, "short": input_url}),
    }
