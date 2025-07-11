# 🚀 Інструкція по автоматичному деплою на VPS

## Огляд варіантів деплою

### 1. 🎯 GitHub Actions (Рекомендовано)
- **Плюси**: Повністю автоматичний, запускається при кожному push
- **Мінуси**: Потребує GitHub репозиторій

### 2. 🔧 Bash скрипти
- **Плюси**: Швидкий, не потребує GitHub
- **Мінуси**: Потребує ручного запуску

---

## 🛠️ Налаштування VPS

### Крок 1: Підготовка SSH ключів
```bash
# Генерація SSH ключа (якщо у вас немає)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Копіювання ключа на VPS
ssh-copy-id user@your-vps-ip
```

### Крок 2: Автоматичне налаштування VPS
```bash
# Надання прав на виконання
chmod +x setup-vps.sh

# Запуск налаштування
./setup-vps.sh YOUR_VPS_IP YOUR_USERNAME ~/.ssh/id_rsa
```

Цей скрипт встановить:
- Docker та Docker Compose
- Git
- Файрвол з необхідними портами
- Директорію для проекту

---

## 🚀 Варіант 1: GitHub Actions

### Налаштування Secrets у GitHub

1. Перейдіть в Settings → Secrets and variables → Actions
2. Додайте наступні secrets:

```
VPS_HOST=your-vps-ip
VPS_USERNAME=your-username
VPS_SSH_KEY=your-private-ssh-key-content
VPS_PORT=22
```

### Отримання SSH ключа
```bash
# Показати приватний ключ
cat ~/.ssh/id_rsa
```

### Первинний деплой
```bash
# На VPS: клонуємо репозиторій
git clone https://github.com/yourusername/telemirror.git
cd telemirror

# Налаштовуємо .env файл
cp .env-example .env
nano .env
```

### Автоматичний деплой
Після налаштування GitHub Actions кожен push в main/master гілку буде автоматично деплоїти аплікацію!

---

## 🔧 Варіант 2: Bash скрипти

### Налаштування та деплой
```bash
# Крок 1: Налаштування VPS
chmod +x setup-vps.sh
./setup-vps.sh YOUR_VPS_IP YOUR_USERNAME ~/.ssh/id_rsa

# Крок 2: Деплой
chmod +x deploy.sh
./deploy.sh YOUR_VPS_IP YOUR_USERNAME ~/.ssh/id_rsa
```

### Щоденне використання
```bash
# Просто запустіть для оновлення
./deploy.sh YOUR_VPS_IP YOUR_USERNAME ~/.ssh/id_rsa
```

---

## 📝 Налаштування .env файлу

Після першого деплою зайдіть на VPS і налаштуйте .env:

```bash
# Підключення до VPS
ssh your-username@your-vps-ip

# Перехід в директорію проекту
cd /home/your-username/telemirror

# Редагування .env файлу
nano .env
```

### Основні змінні:
```env
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
SESSION_STRING=your_session_string
CHAT_MAPPING=[-100source1,-100source2:-100target]
USE_MEMORY_DB=true
LOG_LEVEL=info
```

---

## 🔍 Моніторинг

### Перевірка статусу
```bash
# На VPS
cd /home/your-username/telemirror
docker-compose ps
docker-compose logs -f telemirror
```

### Перезапуск сервісів
```bash
# На VPS
cd /home/your-username/telemirror
docker-compose restart
```

---

## 🆘 Вирішення проблем

### Проблема з правами
```bash
# На VPS
sudo usermod -aG docker $USER
newgrp docker
```

### Проблема з портами
```bash
# Перевірка відкритих портів
sudo ufw status
sudo netstat -tulpn | grep 8000
```

### Очищення Docker
```bash
# На VPS
docker system prune -a
docker volume prune
```

---

## 🎯 Рекомендації

1. **Безпека**: Використовуйте SSH ключі замість паролів
2. **Бекапи**: Регулярно робіть бекапи .env файлу
3. **Моніторинг**: Встановіть Grafana/Prometheus для моніторингу
4. **SSL**: Використовуйте Nginx + Let's Encrypt для HTTPS
5. **Логи**: Регулярно перевіряйте логи аплікації

---

## 📞 Підтримка

Якщо виникли проблеми:
1. Перевірте логи: `docker-compose logs -f`
2. Перевірте статус: `docker-compose ps`
3. Перезапустіть: `docker-compose restart`

**Готово! Ваша аплікація автоматично деплоїться на VPS! 🎉** 