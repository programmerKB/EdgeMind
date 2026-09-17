#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENV_FILE="$ROOT_DIR/.env.prod"
[[ -f $ENV_FILE ]] || ENV_FILE="$ROOT_DIR/.env"
DB_NAME=agent-postgres-prod
BACKEND_NAME=agent-fastapi-prod
FRONTEND_NAME=agent-frontend-prod
NETWORK=edgemind-prod-net
# Keep the legacy volume name so existing production data remains available.
DB_VOLUME=my_agent_project_postgres_prod_data
POSTGRES_IMAGE='postgres:16.15-alpine3.24@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685'

die() { printf '錯誤：%s\n' "$*" >&2; exit 1; }

read_setting() {
  local key=$1 line value='' found=0
  while IFS= read -r line || [[ -n $line ]]; do
    line=${line%$'\r'}
    if [[ $line == "$key="* ]]; then
      value=${line#*=}
      found=1
    fi
  done < "$ENV_FILE"
  if (( found )); then printf '%s' "$value"; fi
}

check_port() {
  local name=$1 port=$2
  [[ $port =~ ^[1-9][0-9]{0,4}$ ]] && (( port <= 65535 )) || die "$name 必須是 1–65535 的連接埠"
}

wait_healthy() {
  local name=$1 status running attempt
  for (( attempt=0; attempt<60; attempt++ )); do
    status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || true)
    [[ $status == healthy ]] && return 0
    running=$(docker inspect --format '{{.State.Running}}' "$name" 2>/dev/null || true)
    [[ $running == true ]] || die "$name 已停止；請執行 docker logs $name"
    sleep 2
  done
  die "$name 未在 120 秒內就緒；請執行 docker logs $name"
}

remove_container() {
  if docker container inspect "$1" >/dev/null 2>&1; then
    docker rm -f -v "$1" >/dev/null
  fi
}

[[ $# -eq 0 ]] || die "此腳本不接受參數"
[[ -f $ENV_FILE ]] || die '找不到 .env.prod 或 .env；請先複製 .env.example 並填入設定'
command -v docker >/dev/null 2>&1 || die '找不到 docker 指令'
docker info >/dev/null 2>&1 || die '無法連接 Docker daemon'

POSTGRES_USER=$(read_setting POSTGRES_USER)
POSTGRES_PASSWORD=$(read_setting POSTGRES_PASSWORD)
POSTGRES_DB=$(read_setting POSTGRES_DB)
DATABASE_URL=$(read_setting DATABASE_URL)
GEMINI_API_KEY=$(read_setting GEMINI_API_KEY)
CORS_ORIGINS=$(read_setting CORS_ORIGINS)
APP_PORT=$(read_setting APP_PORT)
BACKEND_PORT=$(read_setting BACKEND_PORT)
APP_PORT=${APP_PORT:-5173}
BACKEND_PORT=${BACKEND_PORT:-8000}
[[ -n $POSTGRES_USER && -n $POSTGRES_PASSWORD && -n $POSTGRES_DB && -n $DATABASE_URL ]] || die '.env 缺少 PostgreSQL 設定'
[[ -n $GEMINI_API_KEY ]] || die '.env 缺少 GEMINI_API_KEY'
[[ $DATABASE_URL == *'@db:5432/'* ]] || die 'DATABASE_URL 必須連至 Docker 網路中的 db:5432'
[[ -n $CORS_ORIGINS && $CORS_ORIGINS != '*' ]] || die '正式環境的 CORS_ORIGINS 必須列出允許的來源，不能使用 *'
check_port APP_PORT "$APP_PORT"
check_port BACKEND_PORT "$BACKEND_PORT"
[[ $APP_PORT != "$BACKEND_PORT" ]] || die 'APP_PORT 與 BACKEND_PORT 不能相同'
[[ -d $ROOT_DIR/backend/outputs ]] || die '找不到 backend/outputs；請先建立並讓 UID 1000 可寫入'

umask 077
DB_ENV_FILE=$(mktemp)
trap 'rm -f -- "$DB_ENV_FILE"' EXIT
printf 'POSTGRES_USER=%s\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=%s\n' \
  "$POSTGRES_USER" "$POSTGRES_PASSWORD" "$POSTGRES_DB" > "$DB_ENV_FILE"

printf '建置正式映像...\n'
docker build --target production -t edgemind-backend:prod "$ROOT_DIR/backend"
docker build --target production -t edgemind-frontend:prod "$ROOT_DIR/frontend"
docker image inspect "$POSTGRES_IMAGE" >/dev/null 2>&1 || docker pull "$POSTGRES_IMAGE"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null
docker volume create "$DB_VOLUME" >/dev/null

printf '更新正式容器...\n'
remove_container "$FRONTEND_NAME"
remove_container "$BACKEND_NAME"
remove_container "$DB_NAME"

docker run -d --name "$DB_NAME" --network "$NETWORK" --network-alias db \
  --restart unless-stopped --env-file "$DB_ENV_FILE" \
  --mount "type=volume,src=$DB_VOLUME,dst=/var/lib/postgresql/data" \
  --health-cmd 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  --health-interval 5s --health-timeout 5s --health-retries 12 --health-start-period 10s \
  "$POSTGRES_IMAGE" >/dev/null
wait_healthy "$DB_NAME"

docker run -d --name "$BACKEND_NAME" --network "$NETWORK" --network-alias backend \
  --restart unless-stopped --env-file "$ENV_FILE" \
  --env SEED_DEMO_DATA=false --env INFERENCE_OUTPUT_DIR=/app/outputs \
  --publish "127.0.0.1:$BACKEND_PORT:8000" \
  --mount "type=bind,src=$ROOT_DIR/backend/outputs,dst=/app/outputs" \
  edgemind-backend:prod >/dev/null
wait_healthy "$BACKEND_NAME"

docker run -d --name "$FRONTEND_NAME" --network "$NETWORK" \
  --restart unless-stopped --publish "$APP_PORT:8080" \
  edgemind-frontend:prod >/dev/null
wait_healthy "$FRONTEND_NAME"

printf '正式環境已就緒：Web http://localhost:%s；API http://127.0.0.1:%s/docs\n' "$APP_PORT" "$BACKEND_PORT"
