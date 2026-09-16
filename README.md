Plataforma de Revenda de Veículos — Fase 5 (SOAT)
API serverless para uma revenda de veículos: operadores cadastram e editam o estoque, compradores se cadastram, consultam os veículos ordenados por preço e iniciam a compra. O ponto crítico — duas pessoas querendo o mesmo carro, ou um pagamento que nunca acontece — é tratado com reserva atômica e uma SAGA orquestrada com compensação.

Tech Challenge da fase 5 da pós-graduação em Arquitetura de Software (FIAP).

Arquitetura
Serverless na AWS, sem servidor de aplicação e sem banco provisionado:

API Gateway (REST v1) com authorizer JWT do Cognito (grupo admin separa operador de comprador)
Lambda em Python 3.11, um pacote por domínio (veiculos, clientes, compras, pagamentos) e biblioteca compartilhada em src/shared
DynamoDB em modo sob demanda; a reserva do veículo é uma escrita condicional atômica (DISPONIVEL → RESERVADO) — a concorrência é resolvida no banco, não na aplicação. Ordenação por preço via GSI com chave zero-padded
Step Functions: a SAGA de compra é orquestrada, com callback por task token — a máquina suspende a execução enquanto o gateway de pagamento não responde (timeout de 30 min). Aprovação baixa o estoque; recusa, timeout ou falha disparam a compensação, que libera o veículo e cancela a compra
EventBridge: regra agendada (rate(5 minutes)) expira reservas vencidas
KMS: CPF e endereço do comprador cifrados no DynamoDB (LGPD) — até com acesso à tabela, o dado não é legível sem permissão na chave
Secrets Manager: segredo do webhook de pagamento fora do código
Funcionalidades
Cadastro e edição de veículos (marca, modelo, ano, cor, preço)
Listagem de veículos à venda e vendidos, ordenada por preço
Cadastro de compradores (CPF validado, cifrado e mascarado na API)
Compra com reserva anti-corrida e código de pagamento
Confirmação de retirada só para compra paga
Exclusão de dados pessoais (LGPD)
Estrutura
src/                  funções Lambda (um pacote por domínio)
statemachine/         definição ASL da SAGA de compra
template.yaml         infraestrutura SAM
tests/                testes unitários (moto) e E2E (LocalStack)
scripts/              subir LocalStack e implantar localmente
docs/                 openapi.yaml + página Swagger UI

Pré-requisitos
Python 3.11+
uv (ou pip)
Docker
aws-sam-cli-local (SAM CLI apontado para o LocalStack)
uv venv
uv pip install -r requirements.txt -r dev-requirements.txt

Rodando local com LocalStack
./scripts/deploy-local.sh

O script sobe o LocalStack, gera uma variante do template sem autenticação (a LocalStack Community não emula o authorizer Cognito de forma confiável) e implanta a stack. Ao final imprime a URL da API:

API_URL=http://localhost:4566/restapis/<id>/prod/_user_request_

Rodando os testes E2E contra essa URL:

API_URL=<url> AWS_ENDPOINT_URL=http://localhost:4566 pytest -m e2e -v

Testes
pytest -m "not e2e" --cov=src   # unitários (moto), cobertura mínima de 80%

Documentação da API
A especificação OpenAPI está em docs/openapi.yaml. Para explorar interativamente, abra docs/swagger.html no navegador.

CI
O pipeline do GitHub Actions roda em dois estágios: lint (ruff), testes unitários com cobertura, validação do template SAM e da ASL; depois sobe o LocalStack, implanta a stack e roda a suíte E2E.
