# 🔐 Налаштування GitHub Secrets (2 хвилини)

## Крок 1: Отримайте ваш приватний SSH ключ

```bash
# Покажіть вміст вашого приватного SSH ключа
cat ~/.ssh/id_rsa
```

Скопіюйте ВСЕ (включаючи `-----BEGIN OPENSSH PRIVATE KEY-----` та `-----END OPENSSH PRIVATE KEY-----`)

## Крок 2: Додайте Secrets в GitHub

1. Перейдіть у ваш GitHub репозиторій
2. Клікніть **Settings** (у верхньому меню репозиторію)
3. Клікніть **Secrets and variables** → **Actions**
4. Клікніть **New repository secret**

## Крок 3: Додайте ці 4 secrets:

### 1. VPS_HOST
- **Name**: `VPS_HOST`
- **Value**: `123.45.67.89` (ваш IP адрес VPS)

### 2. VPS_USERNAME  
- **Name**: `VPS_USERNAME`
- **Value**: `root` (або ваше ім'я користувача на VPS)

### 3. VPS_SSH_KEY
- **Name**: `VPS_SSH_KEY`  
- **Value**: (вставте вміст вашого приватного SSH ключа з кроку 1)

### 4. VPS_PORT (опціонально)
- **Name**: `VPS_PORT`
- **Value**: `22` (якщо використовуєте інший порт SSH)

## ✅ Готово!

Тепер кожен раз коли ви робите `git push` у main/master гілку, ваша аплікація автоматично деплоїться на VPS!

### Перший деплой:
1. Зробіть push у main гілку
2. Дочекайтесь завершення GitHub Action
3. Зайдіть на VPS і налаштуйте `.env` файл:
   ```bash
   ssh your-username@your-vps-ip
   cd /home/your-username/telemirror
   nano .env
   docker-compose restart
   ```

### Наступні деплої:
Просто робіть `git push` - все відбудеться автоматично! 🚀

---

**Якщо щось не працює:**
1. Перейдіть у **Actions** таб у GitHub репозиторії
2. Клікніть на останній запуск
3. Подивіться логи для діагностики 