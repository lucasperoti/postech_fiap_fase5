import json
import os
import re
import time
import uuid

from botocore.exceptions import ClientError

from shared.auth import resolver_cliente_id
from shared.aws import cliente_aws
from shared.cpf import apenas_digitos, mascarar_cpf, validar_cpf
from shared.crypto import criptografar
from shared.db import tabela
from shared.responses import created, error, ok

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENHA_MINIMA = 8


class EmailJaCadastrado(Exception):
    pass


def _criar_usuario_cognito(email: str, senha: str) -> str:
    cognito = cliente_aws("cognito-idp")
    try:
        resposta = cognito.admin_create_user(
            UserPoolId=os.environ["USER_POOL_ID"],
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            TemporaryPassword=senha,
            MessageAction="SUPPRESS",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "UsernameExistsException":
            raise EmailJaCadastrado(email) from exc
        raise
    cognito.admin_set_user_password(
        UserPoolId=os.environ["USER_POOL_ID"],
        Username=email,
        Password=senha,
        Permanent=True,
    )
    return next(a["Value"] for a in resposta["User"]["Attributes"] if a["Name"] == "sub")


def criar_cliente(event, context):
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return error(400, "JSON_INVALIDO", "Corpo da requisição não é um JSON válido")

    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip()
    cpf = dados.get("cpf") or ""
    if not nome:
        return error(422, "VALIDACAO", "nome é obrigatório")
    if not EMAIL_RE.match(email):
        return error(422, "VALIDACAO", "email inválido")
    if not validar_cpf(cpf):
        return error(422, "CPF_INVALIDO", "CPF inválido")

    senha = dados.get("senha")
    auth_habilitado = bool(os.environ.get("USER_POOL_ID"))
    if auth_habilitado and (not senha or len(senha) < SENHA_MINIMA):
        return error(
            422,
            "VALIDACAO",
            f"senha é obrigatória (mínimo {SENHA_MINIMA} caracteres) quando a autenticação está habilitada",
        )
    if auth_habilitado:
        try:
            cognito_sub = _criar_usuario_cognito(email, senha)
        except EmailJaCadastrado:
            return error(409, "CONFLITO", "Email já cadastrado")

    clientes = tabela("CLIENTES_TABLE")
    cliente_id = str(uuid.uuid4())
    agora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    item = {
        "PK": f"CLIENTE#{cliente_id}",
        "nome": nome,
        "email": email,
        "telefone": dados.get("telefone"),
        "cpf_enc": criptografar(apenas_digitos(cpf)),
        "mascara_cpf": mascarar_cpf(cpf),
        "status": "ATIVO",
        "criado_em": agora,
    }
    if dados.get("endereco"):
        item["endereco_enc"] = criptografar(json.dumps(dados["endereco"], ensure_ascii=False))
    if auth_habilitado:
        item["cognito_sub"] = cognito_sub

    clientes.put_item(Item=item)
    return created(
        {
            "id": cliente_id,
            "nome": nome,
            "email": email,
            "mascara_cpf": item["mascara_cpf"],
            "criado_em": agora,
        }
    )


def excluir_cliente(event, context):
    clientes = tabela("CLIENTES_TABLE")
    cliente_id, erro = resolver_cliente_id(event, clientes)
    if erro:
        return erro
    clientes.update_item(
        Key={"PK": f"CLIENTE#{cliente_id}"},
        UpdateExpression="SET #s = :s REMOVE cpf_enc, endereco_enc, telefone, email",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "EXCLUIDO"},
    )
    return ok({"mensagem": "Dados pessoais removidos (LGPD)"}, status=200)
