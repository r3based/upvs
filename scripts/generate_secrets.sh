#!/bin/bash
# Скрипт для генерации безопасных секретов

echo "🔐 Генерация безопасных секретов для UPVS API"
echo "=============================================="
echo ""

# Генерация API ключа (32 символа)
API_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "API_KEY=$API_KEY"

# Генерация пароля PostgreSQL (32 символа)
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"

# Формируем DATABASE_URL
echo "DATABASE_URL=postgresql://upvs:$POSTGRES_PASSWORD@postgres:5432/upvs"

echo ""
echo "ALLOWED_ORIGINS=https://chat.openai.com,https://your-domain.com"

echo ""
echo "=============================================="
echo "✅ Секреты сгенерированы!"
echo ""
echo "📝 Создайте файл .env и скопируйте туда эти значения:"
echo "   cp .env.example .env"
echo "   nano .env"
echo ""
echo "⚠️  ВАЖНО: Сохраните эти секреты в безопасном месте!"
echo "   Они нужны для восстановления доступа к системе."

