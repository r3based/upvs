#!/bin/bash
# ==============================================================================
# Скрипт настройки Fail2Ban для UPVS API
# ==============================================================================

set -e

echo "🛡️  Настройка Fail2Ban"
echo "======================"
echo ""

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Запустите скрипт с sudo"
    exit 1
fi

# Установка Fail2Ban
if ! command -v fail2ban-client &> /dev/null; then
    echo "📦 Установка Fail2Ban..."
    apt-get update
    apt-get install -y fail2ban
fi

# Создание конфигурации
echo "📝 Создание конфигурации /etc/fail2ban/jail.local..."

cat > /etc/fail2ban/jail.local << 'EOF'
# =============================================================================
# Fail2Ban конфигурация для UPVS API
# =============================================================================

[DEFAULT]
# Время бана (24 часа)
bantime = 24h

# Период поиска (10 минут)
findtime = 10m

# Максимальное количество попыток
maxretry = 3

# Backend для поиска логов
backend = systemd

# Действие при бане
banaction = ufw
action = %(action_)s

[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
maxretry = 3

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/upvs_error.log
maxretry = 5

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/upvs_error.log
maxretry = 10

[nginx-botsearch]
enabled = true
port = http,https
logpath = /var/log/nginx/upvs_access.log
logpath = /var/log/nginx/upvs_error.log
maxretry = 2
EOF

# Перезапуск Fail2Ban
echo "🔄 Перезапуск Fail2Ban..."
systemctl enable fail2ban
systemctl restart fail2ban

# Проверка статуса
echo ""
echo "✅ Fail2Ban настроен и запущен!"
echo ""
echo "📊 Статус:"
fail2ban-client status

echo ""
echo "============================================"
echo "✅ Fail2Ban настроен!"
echo ""
echo "🔒 Активные jail:"
echo "   - sshd (защита SSH)"
echo "   - nginx-http-auth (неудачная аутентификация)"
echo "   - nginx-limit-req (превышение лимитов)"
echo "   - nginx-botsearch (сканирование ботами)"
echo ""
echo "⏰ Параметры:"
echo "   - Время бана: 24 часа"
echo "   - Период анализа: 10 минут"
echo "   - Максимум попыток: 3"
echo ""
echo "📝 Полезные команды:"
echo "   sudo fail2ban-client status sshd"
echo "   sudo fail2ban-client status nginx-http-auth"
echo "   sudo fail2ban-client unban <IP>"
echo "============================================"

