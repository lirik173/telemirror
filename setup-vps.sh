#!/bin/bash

# Скрипт для налаштування VPS для деплою
# Використання: ./setup-vps.sh [host] [username] [ssh_key_path]

set -e

# Кольори для виводу
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Параметри підключення
VPS_HOST=${1:-"your-vps-ip"}
VPS_USERNAME=${2:-"root"}
SSH_KEY_PATH=${3:-"~/.ssh/id_rsa"}

# Перевірка параметрів
if [ "$VPS_HOST" = "your-vps-ip" ]; then
    log_error "Вкажіть IP адресу вашого VPS!"
    echo "Використання: ./setup-vps.sh <VPS_IP> [username] [ssh_key_path]"
    exit 1
fi

log_info "🛠️  Початок налаштування VPS: $VPS_HOST"

# Команди для налаштування VPS
VPS_SETUP_COMMANDS="
set -e

# Оновлення системи
echo '📦 Оновлюємо систему...'
apt-get update -y
apt-get upgrade -y

# Встановлення необхідних пакетів
echo '📦 Встановлюємо базові пакети...'
apt-get install -y curl wget git nano htop ufw

# Налаштування файрволу
echo '🔥 Налаштовуємо файрвол...'
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8000/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Встановлення Docker
echo '🐳 Встановлюємо Docker...'
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER
rm get-docker.sh

# Встановлення Docker Compose
echo '🐳 Встановлюємо Docker Compose...'
curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Налаштування Git (якщо потрібно)
echo '📝 Налаштовуємо Git...'
git config --global user.name \"VPS Deploy\"
git config --global user.email \"deploy@vps.local\"

# Створення директорії для проекту
echo '📁 Створюємо директорію для проекту...'
mkdir -p /home/$USER/telemirror
chown -R $USER:$USER /home/$USER/telemirror

# Встановлення автозапуску Docker
echo '🚀 Налаштовуємо автозапуск Docker...'
systemctl enable docker
systemctl start docker

echo '✅ Налаштування VPS завершено!'
echo '🔧 Встановлено:'
echo '   - Docker: '$(docker --version)
echo '   - Docker Compose: '$(docker-compose --version)
echo '   - Git: '$(git --version)
echo ''
echo '🌐 Порти відкриті:'
echo '   - 22 (SSH)'
echo '   - 8000 (Аплікація)'
echo '   - 80 (HTTP)'
echo '   - 443 (HTTPS)'
echo ''
echo '📂 Директорія проекту: /home/$USER/telemirror'
"

# Виконання команд налаштування на VPS
log_step "🔧 Виконуємо налаштування VPS..."
ssh -i "$SSH_KEY_PATH" "$VPS_USERNAME@$VPS_HOST" "$VPS_SETUP_COMMANDS"

log_info "✅ VPS налаштовано успішно!"
log_info "🚀 Тепер ви можете запустити деплой за допомогою: ./deploy.sh $VPS_HOST $VPS_USERNAME $SSH_KEY_PATH" 