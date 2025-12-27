#!/usr/bin/env bash
# Версия файла: 1.0.0
# Описание: Установка mp_seller_bot с GitHub на сервер в /opt/mp_seller_bot и настройка автозапуска
# Дата изменения: 2025-12-27

set -Eeuo pipefail

APP_DIR_DEFAULT="/opt/mp_seller_bot"
SERVICE_NAME="mp_seller_bot"
BRANCH_DEFAULT="main"

log() {
  echo "[install][$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
  echo "[install][ERROR] $*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Запустите скрипт от root: sudo bash install/install.sh"
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
  return 0
}

install_packages() {
  log "Установка зависимостей (git, curl)..."
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
    die "docker compose не доступен. Проверьте установку docker-compose-plugin."
  fi
}

clone_or_update_repo() {
  local repo_url="$1"
  local app_dir="$2"
  local branch="$3"

  if [[ -z "${repo_url}" ]]; then
    die "Не указан URL репозитория. Пример: https://github.com/kuzkabuh/mp_seller_bot.git"
  fi

  mkdir -p "${app_dir}"

  if [[ -d "${app_dir}/.git" ]]; then
    log "Репозиторий уже существует в ${app_dir}. Выполняю git fetch/pull..."
    cd "${app_dir}"
    git remote set-url origin "${repo_url}"
    git fetch --all --prune
    git checkout "${branch}"
    git pull origin "${branch}"
  else
    log "Клонирую репозиторий ${repo_url} в ${app_dir}..."
    git clone --branch "${branch}" "${repo_url}" "${app_dir}"
    cd "${app_dir}"
  fi

  log "Текущий коммит: $(git rev-parse --short HEAD)"
}

ensure_env_file() {
  local app_dir="$1"
  local env_file="${app_dir}/.env"
  local env_example="${app_dir}/.env.example"

  if [[ -f "${env_file}" ]]; then
    log ".env уже существует: ${env_file}"
    return 0
  fi

  if [[ -f "${env_example}" ]]; then
    log "Создаю .env из .env.example"
    cp "${env_example}" "${env_file}"
  else
    log "Файл .env.example не найден, создаю .env с минимальными параметрами"
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

  log "ВАЖНО: отредактируйте ${env_file} и заполните BOT_TOKEN и FERNET_KEY."
}

create_systemd_service() {
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
  log "systemd unit включен в автозапуск: ${SERVICE_NAME}"
}

start_services() {
  local app_dir="$1"

  log "Запуск контейнеров (docker compose up -d --build)..."
  cd "${app_dir}"
  docker compose up -d --build

  log "Состояние контейнеров:"
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

  log "Готово. Логи: docker logs -f mp_seller_bot_app"
}

print_next_steps() {
  local app_dir="$1"
  log "Следующие шаги:"
  echo "1) Откройте файл: ${app_dir}/.env"
  echo "   - BOT_TOKEN=..."
  echo "   - FERNET_KEY=..."
  echo "2) Перезапустите сервис после правок .env:"
  echo "   systemctl restart ${SERVICE_NAME}.service"
  echo "3) Проверка:"
  echo "   systemctl status ${SERVICE_NAME}.service --no-pager"
  echo "   docker logs -f mp_seller_bot_app"
}

main() {
  require_root

  local repo_url="${1:-}"
  local app_dir="${2:-${APP_DIR_DEFAULT}}"
  local branch="${3:-${BRANCH_DEFAULT}}"

  if [[ -z "${repo_url}" ]]; then
    die "Использование: bash install/install.sh <GIT_REPO_URL> [APP_DIR] [BRANCH]
Пример: bash install/install.sh https://github.com/kuzkabuh/mp_seller_bot.git /opt/mp_seller_bot main"
  fi

  install_packages
  install_docker_if_needed
  clone_or_update_repo "${repo_url}" "${app_dir}" "${branch}"
  ensure_env_file "${app_dir}"
  create_systemd_service "${app_dir}"
  start_services "${app_dir}"
  print_next_steps "${app_dir}"
}

main "$@"
