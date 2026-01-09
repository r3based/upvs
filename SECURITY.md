## 🔒 Руководство по безопасности UPVS API

# Содержание

1. [Обзор](#обзор)
2. [Архитектура безопасности](#архитектура-безопасности)
3. [Быстрый старт (Production Hardening)](#быстрый-старт)
4. [Уровни защиты](#уровни-защиты)
5. [Конфигурация безопасности](#конфигурация-безопасности)
6. [Мониторинг и аудит](#мониторинг-и-аудит)
7. [Incident Response](#incident-response)
8. [Checklist безопасности](#checklist-безопасности)

---

## Обзор

UPVS API реализует **многоуровневую защиту** (Defense in Depth) с минимальной поверхностью атаки.

### Целевое состояние (Target State)

**Снаружи:**
- ✅ Открыт **ТОЛЬКО порт 443** (HTTPS)
- ✅ SSH по ключу (опционально по белому списку IP)
- ✅ Rate limiting на всех уровнях
- ✅ Автоматический бан IP (Fail2Ban)

**Внутри:**
- ✅ FastAPI **не публикуется** наружу
- ✅ PostgreSQL **без внешних портов**
- ✅ Swagger/OpenAPI **отключены**
- ✅ Все `/api/*` требуют **Bearer Token**
- ✅ CORS **ограничен** нужными доменами

---

## Архитектура безопасности

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERNET                              │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS (443 only)
                     │
┌────────────────────▼────────────────────────────────────────┐
│ L1: OS / Linux                                               │
│     - Автообновления безопасности                            │
│     - Базовое hardening                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ L2: Firewall (UFW)                                           │
│     - Deny all incoming (кроме 22, 443)                      │
│     - Allow all outgoing                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ L3: IDS (Fail2Ban)                                           │
│     - SSH brute force protection                             │
│     - HTTP abuse detection                                   │
│     - Auto-ban 24h                                           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ L4: Reverse Proxy (Nginx)                                    │
│     - TLS 1.2+ only                                          │
│     - Rate limiting (5 req/s)                                │
│     - Security headers (HSTS, CSP, etc.)                     │
│     - Блокировка /docs, /openapi.json                        │
└────────────────────┬────────────────────────────────────────┘
                     │ localhost:8000
┌────────────────────▼────────────────────────────────────────┐
│ L5: Application (FastAPI)                                    │
│     - Bearer Token auth на всех /api/*                       │
│     - CORS ограничен                                         │
│     - docs_url/openapi_url = None                            │
└────────────────────┬────────────────────────────────────────┘
                     │ Docker network (internal)
┌────────────────────▼────────────────────────────────────────┐
│ L6: Database (PostgreSQL)                                    │
│     - Без внешних портов                                     │
│     - Сильный пароль                                         │
│     - Encrypted backups                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Быстрый старт

### 🚀 Автоматическая настройка (рекомендуется)

```bash
# 1. Запустите мастер-скрипт
sudo bash scripts/security/setup_all.sh

# Скрипт настроит:
#   - UFW Firewall
#   - Fail2Ban
#   - SSH hardening
#   - Автообновления
#   - Docker logging

# 2. Сгенерируйте секреты
bash scripts/generate_secrets.sh > .env

# 3. Настройте Nginx
sudo cp nginx/upvs-secure.conf /etc/nginx/sites-available/upvs
# Замените your-domain.com на ваш домен!
sudo nano /etc/nginx/sites-available/upvs
sudo ln -s /etc/nginx/sites-available/upvs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 4. Получите SSL сертификат
sudo certbot --nginx -d your-domain.com

# 5. Запустите проект
docker compose up -d

# 6. Экспортируйте OpenAPI (для ChatGPT)
docker compose exec api python scripts/export_openapi.py
```

### ⚙️ Ручная настройка

См. раздел [Уровни защиты](#уровни-защиты) ниже.

---

## Уровни защиты

### L1: OS Security

#### Автообновления

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

#### Базовое hardening

```bash
# Отключить ненужные сервисы
sudo systemctl disable bluetooth.service
sudo systemctl disable cups.service

# Настроить sysctl
cat >> /etc/sysctl.conf << EOF
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.ip_forward = 0
net.ipv6.conf.all.disable_ipv6 = 1
EOF

sudo sysctl -p
```

---

### L2: Firewall (UFW)

```bash
# Политики по умолчанию
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Разрешённые порты
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS

# Опционально: HTTP для Let's Encrypt
sudo ufw allow 80/tcp

# Включить
sudo ufw enable
```

**Или используйте скрипт:**
```bash
sudo bash scripts/security/setup_firewall.sh
```

---

### L3: IDS (Fail2Ban)

```bash
# Установка
sudo apt install fail2ban

# Конфигурация создана в scripts/security/setup_fail2ban.sh
sudo bash scripts/security/setup_fail2ban.sh
```

**Параметры:**
- Ban time: 24 часа
- Find time: 10 минут
- Max retry: 3 попытки

**Защищённые сервисы:**
- SSH (sshd)
- Nginx auth failures
- Nginx rate limit violations
- Nginx bot scanning

---

### L4: Reverse Proxy (Nginx)

Конфигурация в `nginx/upvs-secure.conf`:

**Функции:**
- ✅ TLS 1.2/1.3 only
- ✅ Современные шифры
- ✅ HSTS (1 год)
- ✅ Security headers
- ✅ Rate limiting (5 req/s общий, 2 req/s поиск)
- ✅ Блокировка `/docs`, `/redoc`, `/openapi.json`

**Установка:**
```bash
sudo cp nginx/upvs-secure.conf /etc/nginx/sites-available/upvs
# Замените your-domain.com!
sudo nano /etc/nginx/sites-available/upvs
sudo ln -s /etc/nginx/sites-available/upvs /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### L5: Application (FastAPI)

**Изменения в коде:**

```python
# apps/api/main.py

# 1. Отключены Swagger/OpenAPI
app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# 2. CORS ограничен
allowed_origins = os.getenv("ALLOWED_ORIGINS", "https://chat.openai.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# 3. Bearer Token на всех /api/*
@app.get("/api/tree")
def get_tree(credentials: HTTPAuthorizationCredentials = Security(security)):
    verify_token(credentials)
    ...
```

**Экспорт OpenAPI:**
```bash
docker compose exec api python scripts/export_openapi.py
# Создаст файл openapi.json в корне проекта
```

---

### L6: Database (PostgreSQL)

**Docker configuration:**
```yaml
postgres:
  expose:
    - "5432"  # Только внутри Docker network
  ports: []   # НЕТ внешних портов!
  environment:
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Сильный пароль
```

**Генерация пароля:**
```bash
bash scripts/generate_secrets.sh
```

---

### L7: SSH Hardening

```bash
sudo bash scripts/security/harden_ssh.sh
```

**Настройки:**
- ✅ `PermitRootLogin no`
- ✅ `PasswordAuthentication no`
- ✅ Только ключи
- ✅ `MaxAuthTries 3`
- ✅ Современные алгоритмы

**⚠️ ВАЖНО:** Убедитесь, что у вас настроены SSH ключи ПЕРЕД запуском!

---

## Конфигурация безопасности

### Переменные окружения (.env)

```env
# API Key (32+ символов)
API_KEY=<сгенерированный-ключ>

# PostgreSQL пароль (32+ символов)
POSTGRES_PASSWORD=<сгенерированный-пароль>

# Database URL
DATABASE_URL=postgresql://upvs:<пароль>@postgres:5432/upvs

# CORS домены (через запятую)
ALLOWED_ORIGINS=https://chat.openai.com,https://your-domain.com
```

**Генерация:**
```bash
bash scripts/generate_secrets.sh
```

### Docker изоляция

```yaml
# docker-compose.yml

networks:
  upvs_internal:
    driver: bridge

services:
  api:
    ports:
      - "127.0.0.1:8000:8000"  # ТОЛЬКО localhost!
    networks:
      - upvs_internal
  
  postgres:
    expose:
      - "5432"  # Только внутри network
    ports: []   # НЕТ публичных портов!
    networks:
      - upvs_internal
```

---

## Мониторинг и аудит

### Логи

**Nginx:**
```bash
sudo tail -f /var/log/nginx/upvs_access.log
sudo tail -f /var/log/nginx/upvs_error.log
```

**Fail2Ban:**
```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
sudo fail2ban-client status nginx-http-auth
```

**Docker:**
```bash
docker compose logs -f api
docker compose logs -f postgres
```

### Метрики

**Открытые порты:**
```bash
sudo ss -tulpn
# Должны быть открыты ТОЛЬКО: 22, 80 (опционально), 443
```

**Активные подключения:**
```bash
sudo ss -s
```

**Fail2Ban статистика:**
```bash
sudo fail2ban-client banned
```

### Security scanning

**Порты (снаружи):**
```bash
nmap your-domain.com
# Должен показать ТОЛЬКО 443 (и 80 если разрешён)
```

**SSL/TLS:**
```bash
# Проверка SSL
testssl.sh your-domain.com

# Или онлайн
# https://www.ssllabs.com/ssltest/
```

**Headers:**
```bash
curl -I https://your-domain.com/api/tree
# Проверьте наличие security headers
```

---

## Incident Response

### Подозрительная активность

**1. Проверить логи:**
```bash
# Последние неудачные попытки
sudo journalctl -u sshd | grep "Failed password"

# Забаненные IP
sudo fail2ban-client banned

# Nginx ошибки
sudo tail -100 /var/log/nginx/upvs_error.log
```

**2. Забанить IP вручную:**
```bash
# UFW
sudo ufw deny from 1.2.3.4

# Fail2Ban
sudo fail2ban-client set sshd banip 1.2.3.4
```

**3. Разбанить IP (если ошибочно):**
```bash
sudo fail2ban-client set sshd unbanip 1.2.3.4
sudo ufw delete deny from 1.2.3.4
```

### Компрометация API ключа

**1. Немедленно сменить ключ:**
```bash
# Сгенерировать новый
NEW_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# Обновить .env
nano .env  # Замените API_KEY

# Перезапустить API
docker compose restart api
```

**2. Обновить в ChatGPT Actions**

**3. Проверить логи на несанкционированный доступ:**
```bash
docker compose logs api | grep "401"
```

### Breach (взлом)

**1. Изолировать систему:**
```bash
# Заблокировать все входящие
sudo ufw default deny incoming
```

**2. Сохранить evidence:**
```bash
# Копия логов
mkdir ~/incident_$(date +%Y%m%d)
cp -r /var/log/nginx ~/incident_$(date +%Y%m%d)/
docker compose logs > ~/incident_$(date +%Y%m%d)/docker_logs.txt
```

**3. Восстановление:**
```bash
# Backup БД
docker compose exec postgres pg_dump -U upvs upvs > backup.sql

# Пересоздать все секреты
bash scripts/generate_secrets.sh > .env.new

# Пересобрать контейнеры
docker compose down
docker compose up -d --build
```

---

## Checklist безопасности

### ✅ Перед деплоем

- [ ] Сгенерированы сильные секреты (API_KEY, POSTGRES_PASSWORD)
- [ ] `.env` файл НЕ в Git
- [ ] Docker порты закрыты (только localhost:8000)
- [ ] PostgreSQL без внешних портов
- [ ] Swagger/OpenAPI отключены в коде
- [ ] CORS ограничен нужными доменами

### ✅ После деплоя

- [ ] UFW включён и настроен
- [ ] Fail2Ban работает
- [ ] SSH только по ключу
- [ ] Nginx с SSL (HTTPS)
- [ ] Rate limiting работает
- [ ] Security headers присутствуют
- [ ] `/docs` возвращает 404
- [ ] `/openapi.json` возвращает 404
- [ ] Автообновления настроены

### ✅ Регулярные проверки

**Еженедельно:**
- [ ] Проверить fail2ban статистику
- [ ] Просмотреть логи на аномалии
- [ ] Проверить открытые порты

**Ежемесячно:**
- [ ] Обновить систему
- [ ] Проверить SSL сертификат
- [ ] Ротация секретов (опционально)
- [ ] Backup тест (восстановление)

**Ежеквартально:**
- [ ] Security audit (nmap, testssl)
- [ ] Обновить зависимости Python
- [ ] Проверить CVE для используемых пакетов

---

## Дополнительные меры

### Rate Limiting на уровне API

Добавьте `slowapi` в FastAPI:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/tree")
@limiter.limit("10/minute")
def get_tree(...):
    ...
```

### GeoIP блокировка

В Nginx:
```nginx
# Установить geoip модуль
apt install libnginx-mod-http-geoip

# Блокировать страны
if ($geoip_country_code ~ (CN|RU)) {
    return 403;
}
```

### Web Application Firewall (WAF)

Для дополнительной защиты:
```bash
# ModSecurity + OWASP rules
apt install libapache2-mod-security2
```

### Honeypot

Создайте ложные эндпоинты для детекции сканеров:
```python
@app.get("/admin")
def honeypot():
    logger.warning(f"Honeypot triggered from {request.client.host}")
    return 404
```

---

## Ресурсы

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [Mozilla SSL Config](https://ssl-config.mozilla.org/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

## Контакты

По вопросам безопасности: создайте issue в репозитории проекта.

**⚠️ НЕ публикуйте** чувствительные данные (ключи, пароли, IP адреса) в issue!

---

**Версия:** 2.0.0  
**Последнее обновление:** 2026-01-09

