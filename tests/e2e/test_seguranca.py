import pytest

pytestmark = pytest.mark.e2e


def test_cpf_nunca_exposto_em_claro(api):
    resposta = api.post(
        "/clientes",
        json={"nome": "Ana", "email": "ana@email.com", "cpf": "529.982.247-25"},
    )
    assert resposta.status_code == 201
    assert "52998224725" not in resposta.text
    assert resposta.json()["mascara_cpf"] == "***.***.***-25"


def test_rota_admin_bloqueada_sem_cabecalho(api):
    resposta = api.post(
        "/veiculos",
        json={"marca": "Fiat", "modelo": "Uno", "ano": 2020, "cor": "branco", "preco": 35000.0},
    )
    assert resposta.status_code == 403


def test_webhook_sem_segredo_rejeitado(api):
    resposta = api.post("/pagamentos/webhook", json={"compra_id": "x", "resultado": "APROVADO"})
    assert resposta.status_code == 401
