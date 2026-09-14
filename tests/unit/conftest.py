import boto3
import pytest
from moto import mock_aws


@pytest.fixture()
def aws_mock():
    with mock_aws():
        yield


@pytest.fixture()
def env_vars(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("VEICULOS_TABLE", "veiculos-teste")
    monkeypatch.setenv("CLIENTES_TABLE", "clientes-teste")
    monkeypatch.setenv("COMPRAS_TABLE", "compras-teste")
    monkeypatch.setenv("KMS_KEY_ID", "alias/dados-sensiveis-teste")
    monkeypatch.setenv(
        "WEBHOOK_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:000000000000:secret:webhook"
    )
    monkeypatch.delenv("USER_POOL_ID", raising=False)
    monkeypatch.delenv("SAGA_ARN", raising=False)


@pytest.fixture()
def tabelas(aws_mock, env_vars):
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    criadas = {}
    criadas["compras-teste"] = dynamodb.create_table(
        TableName="compras-teste",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    criadas["veiculos-teste"] = dynamodb.create_table(
        TableName="veiculos-teste",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    criadas["clientes-teste"] = dynamodb.create_table(
        TableName="clientes-teste",
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "cognito_sub", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [{"AttributeName": "cognito_sub", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return criadas
