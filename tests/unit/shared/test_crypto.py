import os

import boto3

from shared.crypto import criptografar, descriptografar


def test_criptografar_e_descriptografar(aws_mock, env_vars):
    kms = boto3.client("kms", region_name="us-east-1")
    chave = kms.create_key(Description="teste")["KeyMetadata"]["Arn"]
    os.environ["KMS_KEY_ID"] = chave
    cifrado = criptografar("52998224725")
    assert cifrado != "52998224725"
    assert descriptografar(cifrado) == "52998224725"
