import os

import boto3


def tabela(nome_var_env: str):
    kwargs = {"region_name": os.environ.get("AWS_REGION", "us-east-1")}
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.Table(os.environ[nome_var_env])
