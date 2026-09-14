import json


def _resposta(payload, status):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False, default=str),
    }


def ok(payload, status=200):
    return _resposta(payload, status)


def created(payload):
    return _resposta(payload, 201)


def error(status, codigo, mensagem):
    return _resposta({"erro": codigo, "mensagem": mensagem}, status)
