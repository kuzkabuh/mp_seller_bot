#!/usr/bin/env bash
# Версия файла: 1.0.1
# Описание: Обновление mp_seller_bot из GitHub по SSH (pull -> rebuild -> restart) с бэкапом .env и возможностью отката.
# Дата изменения: 2025-12-27

# Скрипт предназначен для запуска на сервере в каталоге проекта (обычно /opt/mp_seller_bot).
# Чтобы обновить репозиторий без запроса пароля, необходимо, чтобы у пользователя root
# был корректно настроен SSH‑ключ, разрешённый на GitHub. Скрипт автоматически
# добавит github.com в known_hosts, чтобы избежать интерактивных запросов, и
# принудительно переключит origin на SSH URL. Если ключей нет, скрипт завершится
# с ошибкой и подскажет, как их скопировать.

set -Eeuo pipefail

# Параметры по умолчанию
APP_DIR_DEFAULT="/opt/mp_seller_bot"
SERVICE_NAME="mp_seller_bot"
BRANCH_DEFAULT="main"
# URL репозитория по SSH; можно переопределить через переменную REPO_SSH
REPO_SSH_DEFAULT="git@github.com:kuzkabuh/mp_seller_bot.git"

log() {
  echo "[update][$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
  echo "[update][ERROR] $*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Запустите скрипт от root: sudo bash deploy/update_from_git.sh"
  fi
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
  return 0
}

# Подготавливает SSH-доступ к GitHub: добавляет github.com в known_hosts
# и проверяет наличие приватного ключа. Если ключ не найден, завершает скрипт.
prepare_ssh_for_github() {
  log "Проверка SSH для GitHub..."

  mkdir -p /root/.ssh
  chmod 700 /root/.ssh

  # добавляем fingerprint GitHub, чтобы не было вопроса 'Are you sure you want to continue connecting?'
  if ! grep -q "github.com" /root/.ssh/known_hosts 2>/dev/null; then
    log "Добавляю github.com в known_hosts..."
    ssh-keyscan -H github.com >> /root/.ssh/known_hosts 2>/dev/null || true
    chmod 600 /root/.ssh/known_hosts || true
  fi

  # Проверяем наличие приватных ключей. Этот тест не гарантирует, что ключ корректный,
  # но позволяет поймать частый случай отсутствия ключей у root.
  local key_count
  key_count="$(ls -1 /root/.ssh/id_* 2>/dev/null | grep -E "id_(rsa|ed25519)$" | wc -l | tr -d ' ')"
  if [[ "${key_count}" == "0" ]]; then
    log "В /root/.ssh не найден приватный ключ (id_rsa или id_ed25519)."
    log "Если SSH настроен у другого пользователя, перенесите ключи в /root/.ssh или запускайте обновление от того пользователя."
    log "Пример переноса (осторожно):"
    echo "  sudo mkdir -p /root/.ssh"
    echo "  sudo cp -a /home/<user>/.ssh/id_ed25519 /root/.ssh/"
    echo "  sudo cp -a /home/<user>/.ssh/id_ed25519.pub /root/.ssh/"
    echo "  sudo chmod 700 /root/.ssh && sudo chmod 600 /root/.ssh/id_ed25519 && sudo chmod 644 /root/.ssh/id_ed25519.pub"
    die "SSH ключ для root не найден."
  fi
}

backup_env() {
  local app_dir="$1"
  local env_file="${app_dir}/.env"
  if [[ -f "${env_file}" ]]; then
    local ts
    ts="$(date '+%Y%m%d_%H%M%S')"
    cp -a "${env_file}" "${env_file}.bak_${ts}"
    chmod 600 "${env_file}.bak_${ts}" || true
    log "Бэкап .env создан: ${env_file}.bak_${ts}"
  else
    log ".env не найден, бэкап не требуется."
  fi
}

# Обновляет git-репозиторий: устанавливает origin на SSH URL и делает fetch/pull
update_repo() {
  local app_dir="$1"
  local branch="$2"

  if [[ ! -d "${app_dir}/.git" ]]; then
    die "В ${app_dir} нет git-репозитория. Сначала установите проект через bootstrap."
  fi

  cd "${app_dir}"

  local old_commit
  old_commit="$(git rev-parse --short HEAD)"
  log "Текущий коммит: ${old_commit}"

  # переключаем origin на SSH URL, чтобы git использовал ключи и не спрашивал пароль
  local current_remote
  current_remote="$(git remote get-url origin)"
  local target_remote="${REPO_SSH:-${REPO_SSH_DEFAULT}}"
  if [[ "${current_remote}" != "${target_remote}" ]]; then
    log "Настраиваю origin на ${target_remote}..."
    git remote set-url origin "${target_remote}"
  fi

  log "git fetch..."
  git fetch --all --prune

  log "git checkout ${branch}..."
  git checkout "${branch}"

  log "git pull origin ${branch}..."
  git pull origin "${branch}"

  local new_commit
  new_commit="$(git rev-parse --short HEAD)"
  log "Новый коммит: ${new_commit}"

  if [[ "${old_commit}" == "${new_commit}" ]]; then
    log "Обновлений нет."
  fi
}

rebuild_and_restart() {
  local app_dir="$1"

  if ! need_cmd docker; then
    die "docker не найден."
  fi
  if ! docker compose version >/dev/null 2>&1; then
    die "docker compose не доступен."
  fi

  cd "${app_dir}"

  log "Пересборка и перезапуск контейнеров..."
  docker compose up -d --build

  log "Проверка статуса контейнеров:"
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

restart_systemd_service() {
  if systemctl list-unit-files | grep -q "^${SERVICE_NAME}\.service"; then
    log "Перезапуск systemd сервиса ${SERVICE_NAME}.service"
    systemctl restart "${SERVICE_NAME}.service"
    systemctl status "${SERVICE_NAME}.service" --no-pager || true
  else
    log "systemd сервис ${SERVICE_NAME}.service не найден. Пропускаю."
  fi
}

rollback_to_commit() {
  local app_dir="$1"
  local commit="$2"

  cd "${app_dir}"
  log "Откат к коммиту: ${commit}"
  git reset --hard "${commit}"
  docker compose up -d --build
  restart_systemd_service
  log "Откат выполнен."
}

main() {
  require_root

  local app_dir="${1:-${APP_DIR_DEFAULT}}"
  local branch="${2:-${BRANCH_DEFAULT}}"
  local rollback_commit="${3:-}"

  if [[ ! -d "${app_dir}" ]]; then
    die "Папка проекта не найдена: ${app_dir}"
  fi

  # Подготовка SSH-доступа перед обращением к GitHub
  prepare_ssh_for_github

  # Если указан хэш, выполняем откат и завершаемся
  if [[ -n "${rollback_commit}" ]]; then
    rollback_to_commit "${app_dir}" "${rollback_commit}"
    exit 0
  fi

  backup_env "${app_dir}"
  update_repo "${app_dir}" "${branch}"

  rebuild_and_restart "${app_dir}"
  restart_systemd_service

  log "Готово. Логи: docker logs -f mp_seller_bot_app"
  log "Если нужно откатиться: bash deploy/update_from_git.sh ${app_dir} ${branch} <commit_hash>"
}

main "$@"
