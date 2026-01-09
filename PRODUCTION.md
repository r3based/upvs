# 🚀 Production Deployment Guide

Руководство по деплою UPVS API в продакшен для использования с ChatGPT Actions.

## ⚠️ Важные требования

ChatGPT Actions требует:
- ✅ **HTTPS** (обязательно!)
- ✅ Публичный URL
- ✅ Валидный SSL сертификат
- ✅ Стабильный доступ 24/7

## 🏗️ Варианты деплоя

### Вариант 1: VPS с Docker (Рекомендуется)

**Подходит для:**
- Полный контроль
- Средний и высокий траффик
- Долгосрочное использование

**Провайдеры:**
- DigitalOcean (~$5-10/месяц)
- Hetzner (~€4-8/месяц)
- Vultr (~$5-10/месяц)
- AWS EC2 (больше возможностей, сложнее настройка)

### Вариант 2: Cloud Platform

**Подходит для:**
- Быстрый старт
- Автомасштабирование
- Управляемая инфраструктура

**Платформы:**
- Railway.app
- Render.com
- Fly.io
- Google Cloud Run
- AWS ECS

### Вариант 3: Локальный сервер + ngrok Pro

**Подходит для:**
- Тестирование
- Временное использование

## 📋 Пошаговый деплой на VPS

### Шаг 1: Подготовка сервера

```bash
# 1. Подключитесь к серверу
ssh root@your-server-ip

# 2. Обновите систему
apt update && apt upgrade -y

# 3. Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 4. Установите Docker Compose
apt install docker-compose-plugin -y

# 5. Установите Git
apt install git -y

# 6. Создайте пользователя для приложения (опционально)
adduser upvsapp
usermod -aG docker upvsapp
su - upvsapp
```

### Шаг 2: Клонирование проекта

```bash
# Клонируйте репозиторий
git clone <your-repo-url> upvs
cd upvs

# Или загрузите файлы напрямую
```

### Шаг 3: Настройка данных

```bash
# Убедитесь, что данные на месте
ls -la data/raw/

# Должны быть файлы:
# - pages.csv
# - text_chunks.jsonl
# - tables.jsonl
# - edges.csv
```

### Шаг 4: Настройка переменных

```bash
# Создайте .env файл
nano .env
```

Добавьте:
```env
# Генерируйте сильный ключ!
API_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# Для продакшена можно использовать внешнюю БД
DATABASE_URL=postgresql://upvs:upvs@postgres:5432/upvs
```

Сохраните (Ctrl+O, Enter, Ctrl+X)

### Шаг 5: Запуск приложения

```bash
# Запустите
docker-compose up -d

# Проверьте статус
docker-compose ps

# Проверьте логи
docker-compose logs -f
```

### Шаг 6: Настройка Nginx + SSL

```bash
# Установите Nginx и Certbot
apt install nginx certbot python3-certbot-nginx -y

# Создайте конфиг для вашего домена
nano /etc/nginx/sites-available/upvs
```

Добавьте конфигурацию:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Активируйте конфиг:

```bash
# Создайте симлинк
ln -s /etc/nginx/sites-available/upvs /etc/nginx/sites-enabled/

# Проверьте конфиг
nginx -t

# Перезапустите Nginx
systemctl restart nginx

# Получите SSL сертификат (Let's Encrypt)
certbot --nginx -d your-domain.com

# Certbot автоматически настроит HTTPS и редирект
```

### Шаг 7: Настройка файрвола

```bash
# UFW (Ubuntu)
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw enable

# Проверьте статус
ufw status
```

### Шаг 8: Проверка

```bash
# Проверьте доступность
curl https://your-domain.com/health

# Должен вернуть: {"status":"ok"}

# Проверьте API с ключом
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://your-domain.com/api/tree
```

## 🔐 Безопасность в продакшене

### 1. Сильный API ключ

```bash
# Генерация сильного ключа
openssl rand -base64 32

# Или
head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32
```

### 2. Ограничение rate limiting (опционально)

Добавьте в `apps/api/main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/tree")
@limiter.limit("10/minute")  # Максимум 10 запросов в минуту
def get_full_tree(...):
    ...
```

Не забудьте добавить в requirements.txt:
```
slowapi==0.1.9
```

### 3. Мониторинг логов

```bash
# Настройте ротацию логов Docker
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

systemctl restart docker
```

### 4. Автоматические обновления безопасности

```bash
# Ubuntu
apt install unattended-upgrades -y
dpkg-reconfigure -plow unattended-upgrades
```

### 5. Backup базы данных

```bash
# Создайте скрипт backup
nano /root/backup-upvs.sh
```

Содержимое:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/backups"
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker-compose -f /path/to/docker-compose.yml exec -T postgres \
  pg_dump -U upvs upvs | gzip > $BACKUP_DIR/upvs_$DATE.sql.gz

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "upvs_*.sql.gz" -mtime +7 -delete

echo "Backup completed: upvs_$DATE.sql.gz"
```

```bash
chmod +x /root/backup-upvs.sh

# Добавьте в cron (каждый день в 2 ночи)
crontab -e
```

Добавьте строку:
```
0 2 * * * /root/backup-upvs.sh
```

## 📊 Мониторинг

### Проверка здоровья сервиса

```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Логи API
docker-compose logs -f api --tail=100

# Логи PostgreSQL
docker-compose logs -f postgres --tail=100
```

### Настройка мониторинга (опционально)

Используйте инструменты:
- **Uptime monitoring**: UptimeRobot, StatusCake
- **Logs**: Papertrail, Loggly
- **Metrics**: Prometheus + Grafana
- **Alerts**: Telegram bot, Email

Простой health check скрипт:

```bash
#!/bin/bash
# /root/check-health.sh

URL="https://your-domain.com/health"
TELEGRAM_BOT_TOKEN="your-bot-token"
TELEGRAM_CHAT_ID="your-chat-id"

if ! curl -f -s $URL > /dev/null; then
    MESSAGE="⚠️ UPVS API is DOWN!"
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
         -d chat_id=$TELEGRAM_CHAT_ID \
         -d text="$MESSAGE"
fi
```

Добавьте в cron (каждые 5 минут):
```
*/5 * * * * /root/check-health.sh
```

## 🔄 Обновление приложения

```bash
# 1. Подключитесь к серверу
ssh user@your-server

# 2. Перейдите в директорию проекта
cd /path/to/upvs

# 3. Получите обновления
git pull

# 4. Пересоберите и перезапустите
docker-compose down
docker-compose up -d --build

# 5. Проверьте логи
docker-compose logs -f
```

## 🚨 Troubleshooting

### API не отвечает

```bash
# Проверьте статус
docker-compose ps
systemctl status nginx

# Проверьте логи
docker-compose logs api
tail -f /var/log/nginx/error.log
```

### SSL проблемы

```bash
# Обновите сертификат
certbot renew

# Проверьте валидность
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

### База данных не работает

```bash
# Проверьте статус PostgreSQL
docker-compose exec postgres pg_isready -U upvs

# Проверьте логи
docker-compose logs postgres

# Восстановите из бэкапа
gunzip < /root/backups/upvs_20260109.sql.gz | \
  docker-compose exec -T postgres psql -U upvs -d upvs
```

### Недостаточно памяти

```bash
# Проверьте использование
free -h
docker stats

# Добавьте swap (если нужно)
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

## 💰 Примерные затраты

### VPS (DigitalOcean, Hetzner)
- CPU: 1-2 vCPU
- RAM: 2-4 GB
- Диск: 25-50 GB SSD
- **Стоимость**: $5-12/месяц

### Домен
- **.com**: ~$10-15/год
- **.ru**: ~200-400₽/год

### SSL сертификат
- **Let's Encrypt**: Бесплатно! ✅

### Итого
**~$5-15/месяц** для полноценного продакшн деплоя

## 🎯 Чеклист перед запуском

- [ ] VPS сервер настроен и доступен
- [ ] Docker и Docker Compose установлены
- [ ] Проект склонирован/загружен
- [ ] Данные в `data/raw/` на месте
- [ ] `.env` файл создан с сильным API ключом
- [ ] `docker-compose up -d` успешно запущен
- [ ] Nginx установлен и настроен
- [ ] SSL сертификат получен (Let's Encrypt)
- [ ] Файрвол настроен (UFW)
- [ ] API доступен по HTTPS
- [ ] Health check работает
- [ ] Backup скрипт настроен
- [ ] Мониторинг настроен (опционально)
- [ ] ChatGPT Action настроен и протестирован

## 📚 Полезные ссылки

- [Docker documentation](https://docs.docker.com/)
- [Nginx documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [DigitalOcean tutorials](https://www.digitalocean.com/community/tutorials)
- [UFW tutorial](https://www.digitalocean.com/community/tutorials/ufw-essentials-common-firewall-rules-and-commands)

## 🤝 Поддержка

Если возникли проблемы:
1. Проверьте логи: `docker-compose logs`
2. Проверьте конфигурацию Nginx: `nginx -t`
3. Проверьте доступность: `curl -v https://your-domain.com/health`

---

**Готово к продакшену!** 🎉

