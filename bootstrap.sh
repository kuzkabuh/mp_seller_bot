#!/usr/bin/env bash
# Версия файла: 1.0.0
# Описание: Bootstrap-инсталлер mp_seller_bot (запуск одной командой через curl|bash), установка в /opt/mp_seller_bot
# Дата изменения: 2025-12-27

set -Eeuo pipefail

REPO_URL_DEFAULT="https://github.com/kuzkabuh/mp_seller_bot.git"
BRANCH_DEFAULT="main"
APP_DIR_DEFAULT="/opt/mp_seller_bot"
SERVICE_NAME="mp_seller_bot"

log() {
  echo "[bootstrap][$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
  echo "[bootstrap][ERROR] $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
  return 0
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Запустите от root. Пример: sudo bash <(curl -fsSL .../bootstrap.sh)"
  fi
}

install_base_packages() {
  log "Установка базовых пакетов (git, curl)..."
  apt-get update -y
  apt-get install -y git curl ca-certificates
}

install_docker_if_needed() {
  if need_cmd docker && docker --version >/dev/null 2>&1; then
    log "Docker уже установлен."
  else
    log "Docker не найден. Устанавливаю Docker (официальный репозиторий)..."

    apt-get update -y
    apt-get install -y ca-certificates curl gnupg

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    local arch
    arch="$(dpkg --print-architecture)"

    . /etc/os-release

    echo \
      "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      ${VERSION_CODENAME} stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker

    log "Docker установлен."
  fi

  if docker compose version >/dev/null 2>&1; then
    log "docker compose доступен."
  else
    die "docker compose не доступен. Проверьте docker-compose-plugin."
  fi
}

clone_or_update_repo() {
  local repo_url="$1"
  local app_dir="$2"
  local branch="$3"

  mkdir -p "${app_dir}"

  if [[ -d "${app_dir}/.git" ]]; then
    log "Репозиторий уже есть в ${app_dir}. Обновляю..."
    cd "${app_dir}"
    git remote set-url origin "${repo_url}"
    git fetch --all --prune
    git checkout "${branch}"
    git pull origin "${branch}"
  else
    log "Клонирую ${repo_url} -> ${app_dir} (ветка: ${branch})"
    git clone --branch "${branch}" "${repo_url}" "${app_dir}"
    cd "${app_dir}"
  fi

  log "Коммит: $(git rev-parse --short HEAD)"
}

ensure_env() {
  local app_dir="$1"
  local env_file="${app_dir}/.env"
  local env_example="${app_dir}/.env.example"

  if [[ -f "${env_file}" ]]; then
    log ".env уже существует: ${env_file}"
    chmod 600 "${env_file}" || true
    return 0
  fi

  if [[ -f "${env_example}" ]]; then
    log "Создаю .env из .env.example"
    cp "${env_example}" "${env_file}"
  else
    log "Не найден .env.example — создаю .env с минимальными параметрами"
    cat > "${env_file}" << 'EOF'
BOT_TOKEN=PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE
FERNET_KEY=PUT_YOUR_FERNET_KEY_HERE
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=mp_seller_bot
POSTGRES_USER=mpbot
POSTGRES_PASSWORD=mpbot_password
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
POLL_INTERVAL_SECONDS=60
LOG_LEVEL=INFO
EOF
  fi

  chmod 600 "${env_file}"
  log "Создан ${env_file}. Не забудьте заполнить BOT_TOKEN и FERNET_KEY."
}

create_systemd_unit() {
  local app_dir="$1"

  log "Создаю systemd unit: /etc/systemd/system/${SERVICE_NAME}.service"

  cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=mp_seller_bot (Docker Compose)
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=${app_dir}
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service"
}

start_app() {
  local app_dir="$1"
  log "Запускаю контейнеры..."
  cd "${app_dir}"
  docker compose up -d --build

  log "Контейнеры:"
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

  log "Статус systemd:"
  systemctl restart "${SERVICE_NAME}.service" || true
  systemctl status "${SERVICE_NAME}.service" --no-pager || true
}

print_usage() {
  echo "Использование:"
  echo "  sudo bash <(curl -fsSL https://raw.githubusercontent.com/kuzkabuh/mp_seller_bot/main/bootstrap.sh)"
  echo
  echo "Параметры через ENV (опционально):"
  echo "  REPO_URL=... BRANCH=... APP_DIR=... sudo -E bash <(curl -fsSL .../bootstrap.sh)"
}

main() {
  require_root

  local repo_url="${REPO_URL:-${REPO_URL_DEFAULT}}"
  local branch="${BRANCH:-${BRANCH_DEFAULT}}"
  local app_dir="${APP_DIR:-${APP_DIR_DEFAULT}}"

  log "Параметры:"
  log "  REPO_URL=${repo_url}"
  log "  BRANCH=${branch}"
  log "  APP_DIR=${app_dir}"

  if [[ -z "${repo_url}" ]]; then
    print_usage
    die "REPO_URL пуст."
  fi

  install_base_packages
  install_docker_if_needed
  clone_or_update_repo "${repo_url}" "${app_dir}" "${branch}"
  ensure_env "${app_dir}"
  create_systemd_unit "${app_dir}"
  start_app "${app_dir}"

  log "Готово."
  log "Дальше:"
  echo "1) Откройте: ${app_dir}/.env"
  echo "   - BOT_TOKEN=..."
  echo "   - FERNET_KEY=..."
  echo "2) Примените:"
  echo "   systemctl restart ${SERVICE_NAME}.service"
  echo "3) Логи:"
  echo "   docker logs -f mp_seller_bot_app"
}

main "$@"
