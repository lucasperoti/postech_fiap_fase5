import re


def apenas_digitos(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


def validar_cpf(cpf: str) -> bool:
    digitos = apenas_digitos(cpf)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for i in (9, 10):
        soma = sum(int(digitos[j]) * ((i + 1) - j) for j in range(i))
        digito = (soma * 10 % 11) % 10
        if digito != int(digitos[i]):
            return False
    return True


def mascarar_cpf(cpf: str) -> str:
    digitos = apenas_digitos(cpf)
    return f"***.***.***-{digitos[-2:]}" if len(digitos) == 11 else "***"
