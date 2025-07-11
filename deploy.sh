#!/bin/bash

# Скрипт для автоматичного деплою на VPS
# Використання: ./deploy.sh [host] [username] [key_path]

set -e

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функції для виводу
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Параметри підключення
VPS_HOST=${1:-"your-vps-ip"}
VPS_USERNAME=${2:-"root"}
SSH_KEY_PATH=${3:-"~/.ssh/id_rsa"}
REMOTE_PATH="/home/${VPS_USERNAME}/telemirror"

# Перевірка параметрів
if [ "$VPS_HOST" = "your-vps-ip" ]; then
    log_error "Вкажіть IP адресу вашого VPS!"
    echo "Використання: ./deploy.sh <VPS_IP> [username] [ssh_key_path]"
    exit 1
fi

log_info "🚀 Початок деплою на VPS: $VPS_HOST"

# Перевірка SSH підключення
log_info "🔐 Перевірка SSH підключення..."
if ! ssh -i "$SSH_KEY_PATH" -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USERNAME@$VPS_HOST" exit 2>/dev/null; then
    log_error "Не вдалося підключитися до VPS через SSH"
    exit 1
fi

# Команди для виконання на VPS
SSH_COMMANDS="
set -e

# Перевірка чи існує директорія
if [ ! -d '$REMOTE_PATH' ]; then
    echo '📁 Клонуємо репозиторій...'
    git clone https://github.com/$(git config --get remote.origin.url | sed 's/.*[\/:]//' | sed 's/.git$//')/$REMOTE_PATH
    cd $REMOTE_PATH
else
    echo '📁 Оновлюємо код...'
    cd $REMOTE_PATH
    git pull origin main
fi

# Перевірка чи існує .env файл
if [ ! -f '.env' ]; then
    echo '⚠️  Файл .env не знайдено! Скопіюйте .env-example в .env та налаштуйте'
    cp .env-example .env
    echo '📝 Відредагуйте файл .env перед запуском:'
    echo '    nano .env'
    exit 1
fi

# Встановлення Docker якщо не встановлений
if ! command -v docker &> /dev/null; then
    echo '🐳 Встановлюємо Docker...'
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER
    rm get-docker.sh
fi

# Встановлення Docker Compose якщо не встановлений
if ! command -v docker-compose &> /dev/null; then
    echo '🐳 Встановлюємо Docker Compose...'
    curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Зупинка старих контейнерів
echo '🛑 Зупиняємо старі контейнери...'
docker-compose down || true

# Збірка та запуск
echo '🏗️  Збираємо образи...'
docker-compose build --no-cache

echo '🚀 Запускаємо контейнери...'
docker-compose up -d

# Очищення старих образів
echo '🧹 Очищаємо старі образи...'
docker system prune -f

echo '✅ Деплой завершено успішно!'
echo '📊 Статус контейнерів:'
docker-compose ps
"

# Виконання команд на VPS
log_info "📤 Виконуємо команди на VPS..."
ssh -i "$SSH_KEY_PATH" "$VPS_USERNAME@$VPS_HOST" "$SSH_COMMANDS"

log_info "✅ Деплой завершено успішно!"
log_info "🌐 Ваша аплікація доступна на: http://$VPS_HOST:8000" 