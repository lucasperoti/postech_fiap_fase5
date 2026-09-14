import base64
import os

from shared.aws import cliente_aws


def criptografar(texto: str) -> str:
    blob = cliente_aws("kms").encrypt(
        KeyId=os.environ["KMS_KEY_ID"], Plaintext=texto.encode("utf-8")
    )["CiphertextBlob"]
    return base64.b64encode(blob).decode("ascii")


def descriptografar(cifrado_b64: str) -> str:
    blob = base64.b64decode(cifrado_b64)
    return cliente_aws("kms").decrypt(CiphertextBlob=blob)["Plaintext"].decode("utf-8")
