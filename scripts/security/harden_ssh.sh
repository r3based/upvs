#!/bin/bash
# ==============================================================================
# Скрипт настройки безопасного SSH
# ==============================================================================

set -e

echo "🔐 Настройка безопасного SSH"
echo "============================="
echo ""

# Проверка прав
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Запустите скрипт с sudo"
    exit 1
fi

# Backup текущей конфигурации
echo "💾 Создание backup /etc/ssh/sshd_config..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d-%H%M%S)

# Получить текущего пользователя (не root)
CURRENT_USER="${SUDO_USER:-$USER}"
if [ "$CURRENT_USER" = "root" ]; then
    read -p "👤 Введите имя пользователя для SSH доступа: " CURRENT_USER
fi

echo "📝 Настройка SSH конфигурации..."

# Применяем безопасные настройки
cat > /etc/ssh/sshd_config.d/99-upvs-hardening.conf << EOF
# =============================================================================
# SSH Hardening для UPVS API
# =============================================================================

# Запретить root login
PermitRootLogin no

# Только ключи, без паролей
PasswordAuthentication no
PubkeyAuthentication yes

# Разрешённые пользователи
AllowUsers $CURRENT_USER

# Ограничения
MaxAuthTries 3
MaxSessions 2
LoginGraceTime 30

# Отключить ненужное
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no

# Протокол
Protocol 2

# Сильные алгоритмы
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
EOF

# Проверка конфигурации
echo "✅ Проверка конфигурации SSH..."
if sshd -t; then
    echo "✅ Конфигурация корректна"
else
    echo "❌ Ошибка в конфигурации!"
    echo "Восстанавливаем backup..."
    mv /etc/ssh/sshd_config.backup.* /etc/ssh/sshd_config
    exit 1
fi

# Перезапуск SSH
echo ""
read -p "⚠️  Перезапустить SSH? Убедитесь, что у вас есть SSH ключ! (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 Перезапуск SSH..."
    systemctl restart sshd
    
    echo ""
    echo "✅ SSH настроен и перезапущен!"
else
    echo "⚠️  SSH НЕ перезапущен. Перезапустите вручную: sudo systemctl restart sshd"
fi

echo ""
echo "============================================"
echo "✅ SSH защищён!"
echo ""
echo "🔒 Настройки:"
echo "   - Root login: ОТКЛЮЧЁН"
echo "   - Пароли: ОТКЛЮЧЕНЫ"
echo "   - Только ключи: ДА"
echo "   - Разрешённые пользователи: $CURRENT_USER"
echo "   - Максимум попыток: 3"
echo ""
echo "⚠️  ВАЖНО:"
echo "   1. Убедитесь, что ваш SSH ключ добавлен:"
echo "      cat ~/.ssh/id_rsa.pub | ssh $CURRENT_USER@server 'cat >> ~/.ssh/authorized_keys'"
echo ""
echo "   2. НЕ закрывайте текущую SSH сессию!"
echo "      Откройте новую и проверьте доступ"
echo ""
echo "   3. Если что-то не работает, восстановите backup:"
echo "      sudo cp /etc/ssh/sshd_config.backup.* /etc/ssh/sshd_config"
echo "      sudo systemctl restart sshd"
echo "============================================"

