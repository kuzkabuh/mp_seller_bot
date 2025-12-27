#!/usr/bin/env bash
# Версия файла: 1.0.1
# Описание: Bootstrap-инсталлер mp_seller_bot (одна команда через curl|bash), git clone/pull по SSH, установка в /opt/mp_seller_bot
# Дата изменения: 2025-12-27

set -Eeuo pipefail

# По умолчанию используем SSH-URL (вам подходит, раз SSH настроен)
REPO_SSH_DEFAULT="git@github.com:kuzkabuh/mp_seller_bot.git"
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
  log "Установка базовых пакетов (git, curl, openssh-client)..."
  apt-get update -y
  apt-get install -y git curl ca-certificates openssh-client
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

prepare_ssh_for_github() {
  # Важно: скрипт запускается от root, значит ключи должны быть доступны root'у
  # Если ваш ключ лежит у другого пользователя (например artem), можно:
  # 1) запускать скрипт от этого пользователя, или
  # 2) скопировать ключи в /root/.ssh с корректными правами
  log "Проверка SSH для GitHub..."

  mkdir -p /root/.ssh
  chmod 700 /root/.ssh

  # Добавляем known_hosts, чтобы не было интерактивного запроса
  if ! grep -q "github.com" /root/.ssh/known_hosts 2>/dev/null; then
    log "Добавляю github.com в known_hosts..."
    ssh-keyscan -H github.com >> /root/.ssh/known_hosts 2>/dev/null || true
    chmod 600 /root/.ssh/known_hosts || true
  fi

  # Быстрая проверка наличия приватных ключей
  local key_count
  key_count="$(ls -1 /root/.ssh/id_* 2>/dev/null | grep -E "id_(rsa|ed25519)$" | wc -l | tr -d ' ')"
  if [[ "${key_count}" == "0" ]]; then
    log "В /root/.ssh не найден приватный ключ (id_rsa или id_ed25519)."
    log "Если SSH уже настроен у другого пользователя, перенесите ключи в /root/.ssh или запускайте установку от того пользователя."
    log "Пример переноса (осторожно):"
    echo "  sudo mkdir -p /root/.ssh"
    echo "  sudo cp -a /home/<user>/.ssh/id_ed25519 /root/.ssh/"
    echo "  sudo cp -a /home/<user>/.ssh/id_ed25519.pub /root/.ssh/"
    echo "  sudo chmod 700 /root/.ssh && sudo chmod 600 /root/.ssh/id_ed25519 && sudo chmod 644 /root/.ssh/id_ed25519.pub"
    die "SSH ключ для root не найден."
  fi

  # Проверка доступа к GitHub (не считается ошибкой, если GitHub отвечает кодом 1 с welcome-msg)
  set +e
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -T git@github.com 2>&1 | tee /tmp/github_ssh_test.log >/dev/null
  local rc=$?
  set -e

  if grep -qi "successfully authenticated" /tmp/github_ssh_test.log || grep -qi "You've successfully authenticated" /tmp/github_ssh_test.log; then
    log "SSH-аутентификация GitHub: OK"
    return 0
  fi

  # GitHub часто возвращает rc=1 даже при успешной аутентификации (без shell access)
  if grep -qi "Hi " /tmp/github_ssh_test.log && grep -qi "GitHub does not provide shell access" /tmp/github_ssh_test.log; then
    log "SSH-аутентификация GitHub: OK (no shell access — это нормально)"
    return 0
  fi

  log "Не удалось подтвердить SSH-доступ к GitHub от root."
  log "Вывод проверки сохранён: /tmp/github_ssh_test.log"
  die "Почините SSH-доступ (ключ/права/агент) и повторите."
}

clone_or_update_repo_ssh() {
  local repo_ssh="$1"
  local app_dir="$2"
  local branch="$3"

  mkdir -p "${app_dir}"

  if [[ -d "${app_dir}/.git" ]]; then
    log "Репозиторий уже есть в ${app_dir}. Обновляю по SSH..."
    cd "${app_dir}"
    git remote set-url origin "${repo_ssh}"
    git fetch --all --prune
    git checkout "${branch}"
    git pull origin "${branch}"
  else
    log "Клонирую по SSH ${repo_ssh} -> ${app_dir} (ветка: ${branch})"
    git clone --branch "${branch}" "${repo_ssh}" "${app_dir}"
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
  log "Создан ${env_file}. Заполните BOT_TOKEN и FERNET_KEY."
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

  log "Перезапуск systemd-сервиса (на случай автозапуска):"
  systemctl restart "${SERVICE_NAME}.service" || true
  systemctl status "${SERVICE_NAME}.service" --no-pager || true
}

main() {
  require_root

  local repo_ssh="${REPO_SSH:-${REPO_SSH_DEFAULT}}"
  local branch="${BRANCH:-${BRANCH_DEFAULT}}"
  local app_dir="${APP_DIR:-${APP_DIR_DEFAULT}}"

  log "Параметры:"
  log "  REPO_SSH=${repo_ssh}"
  log "  BRANCH=${branch}"
  log "  APP_DIR=${app_dir}"

  install_base_packages
  install_docker_if_needed
  prepare_ssh_for_github
  clone_or_update_repo_ssh "${repo_ssh}" "${app_dir}" "${branch}"
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
