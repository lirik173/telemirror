#!/bin/bash

# ==============================================
# 🚀 TeleMirror - Швидкий деплой на VPS
# ==============================================

set -e

# Кольори
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Функції виводу
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }
log_success() { echo -e "${PURPLE}[SUCCESS]${NC} $1"; }

# Функція для введення даних
read_input() {
    local prompt="$1"
    local var_name="$2"
    local default_value="$3"
    
    if [ -n "$default_value" ]; then
        echo -e "${BLUE}$prompt${NC} (за замовчуванням: $default_value): "
    else
        echo -e "${BLUE}$prompt${NC}: "
    fi
    
    read -r input
    if [ -z "$input" ] && [ -n "$default_value" ]; then
        eval "$var_name=\"$default_value\""
    else
        eval "$var_name=\"$input\""
    fi
}

# Головний заголовок
echo -e "${PURPLE}"
echo "=================================================="
echo "🚀 TeleMirror - Швидкий деплой на VPS"
echo "=================================================="
echo -e "${NC}"

# Крок 1: Введення даних VPS
log_step "1. Налаштування підключення до VPS"
read_input "IP адреса VPS" VPS_HOST
read_input "Користувач SSH" VPS_USERNAME "root"
read_input "Шлях до SSH ключа" SSH_KEY_PATH "~/.ssh/id_rsa"

# Крок 2: Telegram налаштування
log_step "2. Налаштування Telegram API"
read_input "API_ID (з https://my.telegram.org/apps)" API_ID
read_input "API_HASH (з https://my.telegram.org/apps)" API_HASH
read_input "SESSION_STRING (отримайте через python login.py)" SESSION_STRING

# Крок 3: Налаштування каналів
log_step "3. Налаштування каналів"
log_info "Формат ID каналів: -100XXXXXXXXX"
log_info "Щоб отримати ID каналу, додайте бота @userinfobot до каналу"
read_input "ID джерела каналу" SOURCE_CHAT_ID
read_input "ID цільового каналу" TARGET_CHAT_ID

# Крок 4: Додаткові налаштування
log_step "4. Додаткові налаштування"
read_input "Порт для додатка" PORT_API "8000"
read_input "Порт для PostgreSQL" PORT_PG "5432"
read_input "Рівень логування" LOG_LEVEL "INFO"

# Крок 5: Проксі (опційно)
log_step "5. Проксі налаштування (опційно)"
read_input "Використовувати проксі? (y/n)" USE_PROXY "n"

PROXY_CONFIG=""
if [ "$USE_PROXY" = "y" ] || [ "$USE_PROXY" = "Y" ]; then
    read_input "Тип проксі (socks5/socks4/http)" PROXY_TYPE "socks5"
    read_input "Хост проксі" PROXY_HOST "127.0.0.1"
    read_input "Порт проксі" PROXY_PORT "1080"
    read_input "Ім'я користувача проксі (опційно)" PROXY_USERNAME
    read_input "Пароль проксі (опційно)" PROXY_PASSWORD
    
    PROXY_CONFIG="
PROXY_TYPE=$PROXY_TYPE
PROXY_HOST=$PROXY_HOST
PROXY_PORT=$PROXY_PORT"
    
    if [ -n "$PROXY_USERNAME" ]; then
        PROXY_CONFIG="$PROXY_CONFIG
PROXY_USERNAME=$PROXY_USERNAME
PROXY_PASSWORD=$PROXY_PASSWORD"
    fi
fi

# Створення .env файлу
log_step "6. Створення .env файлу"
cat > .env << EOF
# ==============================================
# 🚀 TeleMirror - Конфігурація для деплою
# ==============================================

# Telegram API
API_ID=$API_ID
API_HASH=$API_HASH
SESSION_STRING=$SESSION_STRING

# База даних
USE_MEMORY_DB=false

# Маппінг каналів
CHAT_MAPPING=[$SOURCE_CHAT_ID:$TARGET_CHAT_ID]

# Налаштування
LOG_LEVEL=$LOG_LEVEL
HOST=0.0.0.0
PORT=$PORT_API

# Порти Docker
PORT_PG=$PORT_PG
PORT_API=$PORT_API

# Повторення
REPEAT_INTERVAL=300
REPEAT_COUNT=3$PROXY_CONFIG
EOF

log_success "Файл .env створено успішно!"

# Крок 7: Деплой
log_step "7. Початок деплою на VPS"
log_info "Перевірка SSH підключення..."

if ! ssh -i "$SSH_KEY_PATH" -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USERNAME@$VPS_HOST" exit 2>/dev/null; then
    log_error "Не вдалося підключитися до VPS через SSH"
    log_info "Перевірте:"
    log_info "- IP адресу VPS: $VPS_HOST"
    log_info "- SSH ключ: $SSH_KEY_PATH"
    log_info "- Користувача: $VPS_USERNAME"
    exit 1
fi

log_success "SSH підключення успішне!"

# Створення архіву проекту
log_step "8. Підготовка файлів для деплою"
tar -czf telemirror-deploy.tar.gz --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' .

# Копіювання файлів на VPS
log_step "9. Копіювання файлів на VPS"
scp -i "$SSH_KEY_PATH" telemirror-deploy.tar.gz "$VPS_USERNAME@$VPS_HOST:/tmp/"

# Виконання команд на VPS
log_step "10. Деплой на VPS"
ssh -i "$SSH_KEY_PATH" "$VPS_USERNAME@$VPS_HOST" << EOF
set -e

# Створення директорії
mkdir -p /home/$VPS_USERNAME/telemirror
cd /home/$VPS_USERNAME/telemirror

# Розпакування
tar -xzf /tmp/telemirror-deploy.tar.gz
rm /tmp/telemirror-deploy.tar.gz

# Встановлення Docker якщо потрібно
if ! command -v docker &> /dev/null; then
    echo "🐳 Встановлюємо Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
    rm get-docker.sh
fi

# Встановлення Docker Compose якщо потрібно
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Встановлюємо Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Зупинка старих контейнерів
echo "🛑 Зупиняємо старі контейнери..."
docker-compose down || true

# Запуск контейнерів
echo "🚀 Запускаємо контейнери..."
docker-compose up -d --build

# Очищення
echo "🧹 Очищаємо старі образи..."
docker system prune -f

echo "✅ Деплой завершено!"
echo "📊 Статус контейнерів:"
docker-compose ps
EOF

# Очищення локального архіву
rm telemirror-deploy.tar.gz

# Фінальна інформація
log_success "🎉 Деплой завершено успішно!"
echo ""
echo -e "${GREEN}=================================================="
echo "🌐 Ваша аплікація доступна на:"
echo "   http://$VPS_HOST:$PORT_API"
echo ""
echo "🛠️  Корисні команди для управління:"
echo "   Логи: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd /home/$VPS_USERNAME/telemirror && docker-compose logs -f'"
echo "   Статус: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd /home/$VPS_USERNAME/telemirror && docker-compose ps'"
echo "   Перезапуск: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd /home/$VPS_USERNAME/telemirror && docker-compose restart'"
echo "   Оновлення: ./quick-deploy.sh"
echo "==================================================${NC}" 