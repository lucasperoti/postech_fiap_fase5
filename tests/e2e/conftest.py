import os

import boto3
import httpx
import pytest

API_URL = os.environ.get("API_URL", "").rstrip("/")


@pytest.fixture(scope="session")
def api():
    if not API_URL:
        pytest.skip("API_URL não definida (rode scripts/deploy-local.sh)")
    with httpx.Client(base_url=API_URL, timeout=30) as cliente:
        yield cliente


@pytest.fixture(scope="session")
def aws():
    return boto3.client(
        "dynamodb",
        region_name="us-east-1",
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@pytest.fixture()
def admin_headers():
    return {"X-Admin": "true"}


def cria_cliente(api, nome="Ana", cpf="529.982.247-25"):
    resposta = api.post(
        "/clientes", json={"nome": nome, "email": f"{nome.lower()}@email.com", "cpf": cpf}
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"], {"X-Cliente-Id": resposta.json()["id"]}


def cria_veiculo(api, admin_headers, preco=35000.0, modelo="Uno"):
    resposta = api.post(
        "/veiculos",
        json={"marca": "Fiat", "modelo": modelo, "ano": 2020, "cor": "branco", "preco": preco},
        headers=admin_headers,
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]
