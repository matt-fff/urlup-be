import json
import sys

import boto3
from sqids import Sqids

from urlup_be.config import Config

conf = Config()
sqids = Sqids()


def split_number(input_number):
    # Convert the number to a string for easier manipulation
    num_str = str(input_number)

    # Check if the number is less than sys.maxsize
    if input_number < sys.maxsize:
        return [input_number]

    # Determine the length of each split based on the length of sys.maxsize
    split_length = len(str(sys.maxsize)) - 1

    # Split the number into chunks
    chunks = [
        int(num_str[i : i + split_length])
        for i in range(0, len(num_str), split_length)
    ]

    return chunks


def shorten(url: str) -> str:
    hashed = hash(url.encode())
    shortened = sqids.encode(split_number(hashed))
    return shortened


def handler(event, context):
    # Initialize DynamoDB client
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(conf.table_name)  # Replace with your table name

    # Extract the URL from the event
    input_url = json.loads(event["body"]).get("url", "")
    shortened = shorten(input_url)

    # Check if the URL is in DynamoDB
    try:
        response = table.get_item(Key={"short": shortened})
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Error accessing DynamoDB"}),
        }

    if "Item" in response:
        # URL found in DynamoDB
        stored_url = response["Item"]["url"]

        if stored_url != input_url:
            # TODO collisions
            print("COLLISION!!!")
    else:
        table.put_item(Item={"url": input_url, "short": shortened})

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"url": input_url, "short": shortened}),
    }
