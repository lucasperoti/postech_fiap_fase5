#!/usr/bin/env bash
set -euo pipefail
./scripts/start-localstack.sh

# Gera variante do template sem autenticação para o ambiente local
# (LocalStack Community não valida authorizer Cognito de forma confiável)
python3 - <<'EOF'
import re

texto = open("template.yaml").read()
texto = re.sub(r"      Auth:\n        Authorizers:\n(?:          .*\n)+        DefaultAuthorizer: CognitoAuth\n", "", texto)
texto = texto.replace("""            Auth:
              Authorizer: NONE
""", "")
# Sem USER_POOL_ID no ambiente local: registro não exige senha nem cria usuário no Cognito
texto = re.sub(
    r"      Environment:\n        Variables:\n          USER_POOL_ID: !Ref UserPool\n", "", texto
)
# Sem o agendador de expiração no ambiente local (o teste E2E invoca a função diretamente)
texto = re.sub(
    r"      Events:\n        ExpiracaoAgendada:\n          Type: Schedule\n          Properties:\n            Schedule: rate\(5 minutes\)\n            Enabled: true\n",
    "",
    texto,
)
open("template.local.yaml", "w").write(texto)
EOF

samlocal build --template-file template.local.yaml
samlocal deploy --template-file .aws-sam/build/template.yaml \
  --stack-name fase5-local --region us-east-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --resolve-s3 --no-confirm-changeset --disable-rollback

# Remove APIs órfãs de deploys anteriores e mantém apenas a mais recente
API_ID=$(AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test python3 - <<'EOF'
import boto3
gw = boto3.client("apigateway", region_name="us-east-1", endpoint_url="http://localhost:4566",
                  aws_access_key_id="test", aws_secret_access_key="test")
apis = [a for a in gw.get_rest_apis()["items"] if a["name"].startswith("fase5-local")]
apis.sort(key=lambda a: a["createdDate"], reverse=True)
for antiga in apis[1:]:
    gw.delete_rest_api(restApiId=antiga["id"])
print(apis[0]["id"])
EOF
)
API_URL="http://localhost:4566/restapis/${API_ID}/prod/_user_request_"
echo "API_URL=${API_URL}"
