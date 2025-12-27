#!/usr/bin/env bash
# Версия файла: 1.0.0
# Описание: Обновление mp_seller_bot из GitHub (pull -> rebuild -> restart) с бэкапом .env и откатом
# Дата изменения: 2025-12-27

set -Eeuo pipefail

APP_DIR_DEFAULT="/opt/mp_seller_bot"
SERVICE_NAME="mp_seller_bot"
BRANCH_DEFAULT="main"

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

update_repo() {
  local app_dir="$1"
  local branch="$2"

  if [[ ! -d "${app_dir}/.git" ]]; then
    die "В ${app_dir} нет git-репозитория. Сначала установите проект install/install.sh"
  fi

  cd "${app_dir}"

  local old_commit
  old_commit="$(git rev-parse --short HEAD)"
  log "Текущий коммит: ${old_commit}"

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
