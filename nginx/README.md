# Nginx конфигурация для UPVS API

## 📄 Файлы

- `upvs-secure.conf` - защищённая продакшн конфигурация с:
  - Rate limiting
  - SSL/TLS настройками
  - Security headers
  - Блокировкой служебных эндпоинтов

## 🚀 Установка

### 1. Скопируйте конфигурацию

```bash
sudo cp nginx/upvs-secure.conf /etc/nginx/sites-available/upvs
```

### 2. Замените домен

Отредактируйте файл и замените `your-domain.com` на ваш домен:

```bash
sudo nano /etc/nginx/sites-available/upvs
```

Найдите и замените (2 места):
```nginx
server_name your-domain.com;
```

### 3. Активируйте конфигурацию

```bash
# Создать симлинк
sudo ln -s /etc/nginx/sites-available/upvs /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезагрузить Nginx
sudo systemctl reload nginx
```

### 4. Получите SSL сертификат

```bash
# Установить Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получить сертификат
sudo certbot --nginx -d your-domain.com

# Certbot автоматически обновит конфигурацию
```

### 5. Проверьте работу

```bash
# Health check
curl https://your-domain.com/health

# Проверка, что Swagger заблокирован
curl https://your-domain.com/docs
# Должно вернуть 404

# Проверка API с Bearer token
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://your-domain.com/api/tree
```

## 🔒 Функции безопасности

### Rate Limiting

- **Общий API**: 5 запросов/сек, burst 10
- **Поиск**: 2 запроса/сек, burst 5
- **Health check**: без ограничений

### Заблокированные эндпоинты

- ❌ `/docs` - Swagger UI
- ❌ `/redoc` - ReDoc
- ❌ `/openapi.json` - OpenAPI schema

Для получения OpenAPI schema используйте:
```bash
docker compose exec api python scripts/export_openapi.py
```

### Security Headers

- ✅ HSTS (1 год)
- ✅ X-Frame-Options: DENY
- ✅ X-Content-Type-Options: nosniff
- ✅ Content-Security-Policy
- ✅ Permissions-Policy

### SSL/TLS

- ✅ TLS 1.2, 1.3
- ✅ Современные шифры
- ✅ OCSP Stapling
- ✅ Автоматическое обновление (Certbot)

## 📊 Мониторинг

### Просмотр логов

```bash
# Access logs
sudo tail -f /var/log/nginx/upvs_access.log

# Error logs
sudo tail -f /var/log/nginx/upvs_error.log
```

### Проверка rate limiting

```bash
# Отправить много запросов быстро
for i in {1..20}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
       -H "Authorization: Bearer YOUR_KEY" \
       https://your-domain.com/api/tree
done

# Должны появиться 503 ответы (rate limited)
```

## 🔧 Настройка

### Изменить rate limits

Отредактируйте в `/etc/nginx/sites-available/upvs`:

```nginx
# Увеличить лимит
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

# Или для конкретного location
location /api/ {
    limit_req zone=api burst=20 nodelay;
    ...
}
```

### Добавить дополнительные домены

```nginx
server_name your-domain.com www.your-domain.com;
```

И получите сертификат для всех:
```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

### Белый список IP

Для ограничения доступа к API только с определённых IP:

```nginx
location /api/ {
    # Разрешить только эти IP
    allow 1.2.3.4;
    allow 5.6.7.0/24;
    deny all;
    
    # Остальная конфигурация
    ...
}
```

## 🚨 Troubleshooting

### 502 Bad Gateway

```bash
# Проверить, что API запущен
docker compose ps api

# Проверить логи API
docker compose logs api

# Проверить, что Nginx может подключиться
curl http://127.0.0.1:8000/health
```

### 503 Too Many Requests

Это нормально - работает rate limiting. Для увеличения лимитов см. раздел "Настройка".

### SSL ошибки

```bash
# Проверить сертификаты
sudo certbot certificates

# Обновить сертификат вручную
sudo certbot renew

# Проверить SSL конфигурацию
sudo nginx -t
```

## 📚 Дополнительные ресурсы

- [Nginx документация](https://nginx.org/ru/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Security Headers тест](https://securityheaders.com/)

