import json
from pathlib import Path


def _maquina():
    caminho = Path(__file__).parents[3] / "statemachine" / "purchase_saga.asl.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_estados_obrigatorios_existem():
    maquina = _maquina()
    for estado in (
        "AguardarPagamento",
        "VerificarResultado",
        "MotivoRecusa",
        "ConfirmarVenda",
        "Compensar",
    ):
        assert estado in maquina["States"]


def test_callback_com_task_token():
    maquina = _maquina()
    aguardar = maquina["States"]["AguardarPagamento"]
    assert aguardar["Resource"] == "arn:aws:states:::lambda:invoke.waitForTaskToken"
    assert aguardar["Parameters"]["Payload"]["taskToken.$"] == "$$.Task.Token"


def test_todo_caminho_termina():
    maquina = _maquina()
    for estado in maquina["States"].values():
        if estado["Type"] == "Task":
            assert "Next" in estado or "Catch" in estado
    assert maquina["States"]["CompraConcluida"]["Type"] == "Succeed"
    assert maquina["States"]["CompraCancelada"]["Type"] == "Succeed"


def test_substituicoes_usadas_definidas():
    maquina = _maquina()
    texto = json.dumps(maquina)
    for chave in ("AguardarPagamentoFnArn", "ConfirmarVendaFnArn", "LiberarReservaFnArn"):
        assert f"${{{chave}}}" in texto
