# ⚡ Швидкий старт автоматичного деплою

## ✅ Чек-лист (5 хвилин)

### 1. 🔐 Налаштуйте SSH доступ до VPS
```bash
# Якщо у вас немає SSH ключа - створіть його
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Скопіюйте SSH ключ на VPS
ssh-copy-id your-username@your-vps-ip

# Перевірте підключення
ssh your-username@your-vps-ip
```

### 2. 📋 Додайте GitHub Secrets
У вашому GitHub репозиторії: **Settings** → **Secrets and variables** → **Actions**

Додайте:
- `VPS_HOST` = IP адрес вашого VPS
- `VPS_USERNAME` = ім'я користувача на VPS  
- `VPS_SSH_KEY` = вміст файлу `~/.ssh/id_rsa`
- `VPS_PORT` = 22 (або інший SSH порт)

### 3. 🚀 Запустіть деплой
```bash
git add .
git commit -m "Setup auto deploy"
git push origin main
```

### 4. 📝 Налаштуйте .env після деплою
```bash
# Зайдіть на VPS
ssh your-username@your-vps-ip

# Перейдіть в директорію проекту
cd /home/your-username/telemirror

# Відредагуйте .env файл
nano .env

# Перезапустіть контейнери
docker-compose restart
```

## 🎯 Результат

✅ **Автоматичний деплой** при кожному `git push`  
✅ **Автоматичне встановлення** Docker, Git, файрвол  
✅ **Автоматичне клонування** репозиторію  
✅ **Автоматична збірка** і запуск контейнерів  
✅ **Детальні логи** процесу деплою  

---

## 🔍 Моніторинг

### Перевірка статусу на VPS:
```bash
ssh your-username@your-vps-ip
cd /home/your-username/telemirror

# Статус контейнерів
docker-compose ps

# Логи аплікації
docker-compose logs -f telemirror

# Перезапуск якщо потрібно
docker-compose restart
```

### Перевірка GitHub Actions:
1. Перейдіть у **Actions** таб вашого репозиторію
2. Подивіться статус останнього деплою
3. Клікніть на деплой для перегляду детальних логів

## 🌐 Доступ до аплікації

Після успішного деплою ваша аплікація буде доступна на:
`http://your-vps-ip:8000`

---

**Готово! Тепер просто робіть `git push` і ваша аплікація автоматично оновиться на VPS! 🚀** 