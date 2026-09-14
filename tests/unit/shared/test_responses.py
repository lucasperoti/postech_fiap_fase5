import json

from shared.responses import created, error, ok


def test_ok():
    r = ok({"a": 1})
    assert r["statusCode"] == 200
    assert json.loads(r["body"]) == {"a": 1}


def test_created():
    assert created({"a": 1})["statusCode"] == 201


def test_error():
    r = error(409, "VEICULO_INDISPONIVEL", "Veículo já reservado ou vendido")
    assert r["statusCode"] == 409
    assert json.loads(r["body"])["erro"] == "VEICULO_INDISPONIVEL"
