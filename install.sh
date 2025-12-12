#!/bin/bash

echo "====================================="
echo "  Telegram Stream Bot - Встановлення"
echo "====================================="
echo ""

# Перевірка Python
echo "📦 Перевірка Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не встановлено!"
    echo "Встановіть: sudo apt-get install python3 python3-pip"
    exit 1
fi

# Перевірка FFmpeg
echo "📦 Перевірка FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  FFmpeg не встановлено!"
    echo "Встановлення FFmpeg..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg
fi

# Створення віртуального середовища
echo "🐍 Створення віртуального середовища..."
python3 -m venv venv
source venv/bin/activate

# Встановлення залежностей
echo "📚 Встановлення залежностей..."
pip install --upgrade pip
pip install -r requirements.txt

# Створення .env файлу
if [ ! -f ".env" ]; then
    echo "📝 Створення .env файлу..."
    cp .env.example .env
    echo ""
    echo "⚠️  ВАЖЛИВО: Відредагуйте файл .env та додайте ваш токен бота!"
    echo "nano .env"
fi

# Створення systemd сервісу (опціонально)
echo ""
echo "🔧 Бажаєте створити системний сервіс для автозапуску? (y/n)"
read -r response
if [[ "$response" == "y" || "$response" == "Y" ]]; then
    SERVICE_FILE="/etc/systemd/system/telegram-stream-bot.service"
    CURRENT_DIR=$(pwd)
    
    sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Telegram Stream Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment="PATH=$CURRENT_DIR/venv/bin"
ExecStart=$CURRENT_DIR/venv/bin/python stream_bot_advanced.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    echo "✅ Сервіс створено!"
    echo ""
    echo "Команди управління:"
    echo "  sudo systemctl start telegram-stream-bot   # Запустити"
    echo "  sudo systemctl stop telegram-stream-bot    # Зупинити"
    echo "  sudo systemctl restart telegram-stream-bot # Перезапустити"
    echo "  sudo systemctl status telegram-stream-bot  # Статус"
    echo "  sudo systemctl enable telegram-stream-bot  # Автозапуск"
fi

echo ""
echo "====================================="
echo "✅ Встановлення завершено!"
echo ""
echo "Наступні кроки:"
echo "1. Відредагуйте .env файл: nano .env"
echo "2. Додайте токен вашого бота"
echo "3. Запустіть бота: python3 stream_bot_advanced.py"
echo "====================================="
