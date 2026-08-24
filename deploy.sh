#!/usr/bin/env bash
# ==========================================
# FunPay Bot - 1-Click Linux VPS Deploy Script
# ==========================================

set -e

echo "=========================================="
echo "🚀 FunPay Bot - Автоустановка на сервер"
echo "=========================================="

# Check root
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Пожалуйста, запустите скрипт с правами root (sudo bash deploy.sh)"
  exit 1
fi

# Update packages
echo "[*] Обновление пакетов системы..."
apt-get update -y && apt-get upgrade -y
apt-get install -y python3 python3-pip python3-venv git curl build-essential

# Create storage dirs
mkdir -p storage/logs storage/goods

# Virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Создание виртуального окружения .venv..."
    python3 -m venv .venv
fi

echo "[*] Установка зависимостей..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# If .env does not exist or empty, run setup wizard
if [ ! -f ".env" ]; then
    echo ""
    echo "=========================================="
    echo "🔑 Запуск мастера настройки ключей..."
    echo "=========================================="
    .venv/bin/python setup_wizard.py
fi

# Setup systemd service
echo "[*] Настройка службы автозапуска (systemd)..."
CURRENT_DIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/funpaybot.service"

cat > $SERVICE_FILE <<EOF
[Unit]
Description=FunPay Automation Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/.venv/bin/python main.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable funpaybot
systemctl restart funpaybot

echo ""
echo "=========================================="
echo "✅ FunPay Bot успешно установлен и запущен!"
echo "=========================================="
echo "📌 Полезные команды на сервере:"
echo "  • Статус бота:    systemctl status funpaybot"
echo "  • Просмотр логов: journalctl -u funpaybot -f"
echo "  • Перезапуск:     systemctl restart funpaybot"
echo "  • Остановка:      systemctl stop funpaybot"
echo "  • Настройка:      .venv/bin/python setup_wizard.py"
echo "=========================================="
