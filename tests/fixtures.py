import os

import boto3
import pytest
from moto import mock_dynamodb

os.environ["DDB_TABLE"] = "testTable"


# Function to create DynamoDB table for testing
@pytest.fixture(scope="function")
def dynamodb_table(dynamodb):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.create_table(
        TableName=os.environ["DDB_TABLE"],
        KeySchema=[
            {"AttributeName": "short", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "short", "AttributeType": "S"},
        ],
        ProvisionedThroughput={
            "ReadCapacityUnits": 1,
            "WriteCapacityUnits": 1,
        },
    )
    return table


# The actual test case
@pytest.fixture(scope="function", autouse=True)
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_REGION"] = "us-west-2"


@pytest.fixture()
def dynamodb():
    with mock_dynamodb():
        yield boto3.client("dynamodb")
