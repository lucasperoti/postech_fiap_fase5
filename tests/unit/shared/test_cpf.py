from shared.cpf import apenas_digitos, mascarar_cpf, validar_cpf


def test_cpf_valido_com_formatacao():
    assert validar_cpf("529.982.247-25") is True


def test_cpf_valido_sem_formatacao():
    assert validar_cpf("52998224725") is True


def test_cpf_invalido_dv():
    assert validar_cpf("529.982.247-26") is False


def test_cpf_todos_digitos_iguais():
    assert validar_cpf("111.111.111-11") is False


def test_cpf_curto():
    assert validar_cpf("123") is False


def test_apenas_digitos():
    assert apenas_digitos("529.982.247-25") == "52998224725"


def test_mascarar_cpf():
    assert mascarar_cpf("529.982.247-25") == "***.***.***-25"
