#!/usr/bin/env python3
"""
Telegram Stream Bot - Покращена версія з підтримкою .env
"""

import os
import subprocess
import signal
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import json
from dotenv import load_dotenv

# Завантаження змінних середовища
load_dotenv()

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфігурація з .env
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
MAX_STREAMS_PER_USER = int(os.getenv('MAX_STREAMS_PER_USER', '1'))
FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')

# Словник для збереження активних процесів
active_streams: Dict[int, Dict[str, any]] = {}

# Збережені конфігурації користувачів
saved_configs: Dict[int, list] = {}

# Шлях до файлу збереження конфігурацій
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'saved_configs.json')

# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def load_configs():
    """Завантаження збережених конфігурацій з файлу"""
    global saved_configs
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                # Конвертуємо ключі назад в int
                data = json.load(f)
                saved_configs = {int(k): v for k, v in data.items()}
                logger.info(f"Завантажено конфігурацій для {len(saved_configs)} користувачів")
        else:
            saved_configs = {}
            logger.info("Файл конфігурацій не знайдено, створюється новий")
    except Exception as e:
        logger.error(f"Помилка завантаження конфігурацій: {e}")
        saved_configs = {}

def save_configs():
    """Збереження конфігурацій у файл"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved_configs, f, ensure_ascii=False, indent=2)
        logger.info("Конфігурації збережено успішно")
    except Exception as e:
        logger.error(f"Помилка збереження конфігурацій: {e}")

class StreamConfig:
    """Конфігурація для стріму"""
    def __init__(self, stream_url: str, rtmp_url: str, name: str = "Stream"):
        self.stream_url = stream_url
        self.rtmp_url = rtmp_url
        self.name = name
        self.start_time = datetime.now()

    def get_ffmpeg_command(self) -> list:
        """Генерує команду FFmpeg"""
        return [
            FFMPEG_PATH,
            '-re',
            '-i', self.stream_url,
            '-f', 'lavfi',
            '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-pix_fmt', 'yuv420p',
            '-g', '25',
            '-vf', 'scale=1280:720,format=yuv420p,colorspace=all=bt709:range=tv,fps=25',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ac', '2',
            '-shortest',
            '-f', 'flv',
            self.rtmp_url
        ]

    def to_dict(self) -> dict:
        """Конвертує конфігурацію в словник"""
        return {
            'name': self.name,
            'stream_url': self.stream_url,
            'rtmp_url': self.rtmp_url
        }

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обробка команди /start"""
    user_name = message.from_user.first_name or "Користувач"
    is_admin = message.from_user.id in ADMIN_IDS
    
    await message.answer(
        f"👋 Привіт, <b>{user_name}!</b>\n\n"
        "🎥 <b>Telegram Stream Bot</b>\n\n"
        "📋 <b>Основні команди:</b>\n"
        "▫️ /stream [stream_url] [rtmp_url] - Запустити трансляцію\n"
        "▫️ /stop - Зупинити всі трансляції\n"
        "▫️ /stop_id [id] - Зупинити конкретну трансляцію\n"
        "▫️ /status - Статус трансляцій\n\n"
        "💾 <b>Збережені конфігурації:</b>\n"
        "▫️ /save [name] [stream_url] [rtmp_url] - Зберегти конфіг\n"
        "▫️ /list - Список збережених конфігів\n"
        "▫️ /run [name] - Запустити збережений конфіг\n"
        "▫️ /delete [name] - Видалити конфіг\n\n"
        "▫️ /config - Завантажити JSON конфігурацію\n"
        "▫️ /help - Детальна допомога\n"
        f"\n{'👑 <b>Адмін режим активний</b>' if is_admin else ''}",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обробка команди /help"""
    await message.answer(
        "📚 <b>Детальна допомога</b>\n\n"
        "<b>🎥 Запуск трансляції:</b>\n"
        "<code>/stream [URL стріму] [RTMP URL]</code>\n"
        "• URL - посилання на m3u8/mp4 потік\n"
        "• RTMP URL - повна адреса: rtmps://dc4-1.rtmp.t.me/s/channel_id:key\n\n"
        "<b>💾 Збережені конфігурації:</b>\n"
        "Ви можете зберігати часто використовувані налаштування:\n"
        "<code>/save webcam https://cam.url/stream.m3u8 rtmps://dc4-1.rtmp.t.me/s/1424308297:key</code>\n"
        "<code>/run webcam</code> - швидкий запуск\n\n"
        "<b>📄 JSON конфігурація:</b>\n"
        "Надішліть файл .json з командою /config:\n"
        "<code>{\n"
        '  "stream_url": "https://...",\n'
        '  "rtmp_url": "rtmps://dc4-1.rtmp.t.me/s/channel:key",\n'
        '  "name": "My Stream"\n'
        "}</code>\n\n"
        "<b>⚙️ Технічні деталі:</b>\n"
        "• Формат відео: 1280x720, 25fps, H.264\n"
        "• Аудіо: AAC, 128kbps, стерео\n"
        "• Максимум трансляцій на користувача: " + str(MAX_STREAMS_PER_USER) + "\n\n"
        "⚠️ <b>Важливо:</b>\n"
        "• FFmpeg повинен бути встановлений на сервері\n"
        "• Стабільне з'єднання для безперервної трансляції\n"
        "• RTMP URL має бути дійсним для Telegram",
        parse_mode="HTML"
    )

async def start_stream(message: Message, stream_url: str, rtmp_url: str, name: str = "Stream"):
    """Внутрішня функція для запуску трансляції"""
    user_id = message.from_user.id

    # Перевірка кількості активних стрімів
    user_streams = active_streams.get(user_id, {})
    if len(user_streams) >= MAX_STREAMS_PER_USER:
        await message.answer(
            f"⚠️ Досягнуто ліміт трансляцій ({MAX_STREAMS_PER_USER})!\n"
            "Зупиніть одну з активних командою /stop_id"
        )
        return

    # Створення конфігурації
    config = StreamConfig(stream_url, rtmp_url, name)
    
    try:
        # Запуск FFmpeg процесу
        process = subprocess.Popen(
            config.get_ffmpeg_command(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Генерація ID для стріму
        stream_id = f"stream_{len(user_streams) + 1}"
        
        # Збереження процесу та конфігурації
        if user_id not in active_streams:
            active_streams[user_id] = {}
        
        active_streams[user_id][stream_id] = {
            'process': process,
            'config': config,
            'pid': process.pid
        }
        
        await message.answer(
            "✅ <b>Трансляція запущена!</b>\n\n"
            f"🆔 ID: <code>{stream_id}</code>\n"
            f"📹 URL: <code>{stream_url}</code>\n"
            f"🔑 RTMP: <code>{rtmp_url[:50]}...</code>\n"
            f"⚙️ PID: {process.pid}\n"
            f"⏱ Час запуску: {config.start_time.strftime('%H:%M:%S')}\n\n"
            f"Для зупинки: /stop_id {stream_id}",
            parse_mode="HTML"
        )
        
        # Асинхронний моніторинг процесу
        asyncio.create_task(monitor_stream(user_id, stream_id, process, message.chat.id))
        
    except FileNotFoundError:
        await message.answer(
            "❌ FFmpeg не знайдено!\n"
            "Переконайтеся, що FFmpeg встановлено:\n"
            "<code>sudo apt-get install ffmpeg</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Помилка запуску трансляції: {e}")
        await message.answer(
            f"❌ Помилка запуску трансляції:\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )

@dp.message(Command("stream"))
async def cmd_stream(message: Message):
    """Запуск трансляції"""
    # Парсинг аргументів
    args = message.text.split(maxsplit=2)
    if len(args) != 3:
        await message.answer(
            "❌ Невірний формат команди!\n\n"
            "Використовуйте:\n"
            "<code>/stream [URL стріму] [RTMP URL]</code>\n\n"
            "Приклад:\n"
            "<code>/stream https://example.com/stream.m3u8 rtmps://dc4-1.rtmp.t.me/s/1424308297:key</code>",
            parse_mode="HTML"
        )
        return

    _, stream_url, rtmp_url = args
    await start_stream(message, stream_url, rtmp_url)

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Зупинка всіх трансляцій користувача"""
    user_id = message.from_user.id
    
    if user_id not in active_streams or not active_streams[user_id]:
        await message.answer("ℹ️ У вас немає активних трансляцій")
        return
    
    stopped_count = 0
    for stream_id, stream_data in list(active_streams[user_id].items()):
        process = stream_data['process']
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            stopped_count += 1
        except Exception as e:
            logger.error(f"Помилка зупинки процесу {process.pid}: {e}")
    
    active_streams[user_id].clear()
    
    await message.answer(
        f"⏹ <b>Зупинено трансляцій: {stopped_count}</b>",
        parse_mode="HTML"
    )

@dp.message(Command("stop_id"))
async def cmd_stop_id(message: Message):
    """Зупинка конкретної трансляції за ID"""
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) != 2:
        await message.answer(
            "❌ Вкажіть ID трансляції:\n"
            "Приклад: <code>/stop_id stream_1</code>",
            parse_mode="HTML"
        )
        return
    
    stream_id = args[1]
    
    if user_id not in active_streams or stream_id not in active_streams[user_id]:
        await message.answer(f"❌ Трансляція {stream_id} не знайдена")
        return
    
    stream_data = active_streams[user_id][stream_id]
    process = stream_data['process']
    
    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        
        del active_streams[user_id][stream_id]
        
        await message.answer(
            f"⏹ <b>Трансляція {stream_id} зупинена</b>\n"
            f"PID {process.pid} завершено",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Помилка зупинки трансляції: {e}")
        await message.answer(f"❌ Помилка: {str(e)}")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Статус всіх трансляцій"""
    user_id = message.from_user.id
    
    if user_id not in active_streams or not active_streams[user_id]:
        await message.answer("ℹ️ У вас немає активних трансляцій")
        return
    
    status_text = "📊 <b>Статус трансляцій:</b>\n\n"
    
    for stream_id, stream_data in active_streams[user_id].items():
        process = stream_data['process']
        config = stream_data['config']
        
        poll = process.poll()
        if poll is None:
            status = "🟢 Активна"
            uptime = datetime.now() - config.start_time
            uptime_str = str(uptime).split('.')[0]
        else:
            status = f"🔴 Завершена (код: {poll})"
            uptime_str = "—"
            
        status_text += (
            f"<b>{stream_id}:</b>\n"
            f"  Статус: {status}\n"
            f"  PID: {process.pid}\n"
            f"  Час роботи: {uptime_str}\n"
            f"  URL: <code>{config.stream_url[:30]}...</code>\n\n"
        )
    
    await message.answer(status_text, parse_mode="HTML")

@dp.message(Command("save"))
async def cmd_save(message: Message):
    """Зберегти конфігурацію"""
    user_id = message.from_user.id
    args = message.text.split(maxsplit=3)
    
    if len(args) != 4:
        await message.answer(
            "❌ Невірний формат!\n"
            "<code>/save [назва] [URL] [RTMP URL]</code>\n\n"
            "Приклад:\n"
            "<code>/save webcam https://cam.url/stream.m3u8 rtmps://dc4-1.rtmp.t.me/s/1424308297:key</code>",
            parse_mode="HTML"
        )
        return

    _, name, stream_url, rtmp_url = args
    
    if user_id not in saved_configs:
        saved_configs[user_id] = []
    
    # Перевірка на дублікати
    for config in saved_configs[user_id]:
        if config['name'] == name:
            config['stream_url'] = stream_url
            config['rtmp_url'] = rtmp_url
            save_configs()  # Зберігаємо зміни
            await message.answer(f"♻️ Конфігурацію '{name}' оновлено")
            return

    saved_configs[user_id].append({
        'name': name,
        'stream_url': stream_url,
        'rtmp_url': rtmp_url
    })
    save_configs()  # Зберігаємо зміни

    await message.answer(
        f"💾 Конфігурацію '<b>{name}</b>' збережено!\n"
        f"Запуск: /run {name}",
        parse_mode="HTML"
    )

@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Список збережених конфігурацій"""
    user_id = message.from_user.id
    
    if user_id not in saved_configs or not saved_configs[user_id]:
        await message.answer("📭 У вас немає збережених конфігурацій")
        return
    
    text = "📋 <b>Збережені конфігурації:</b>\n\n"
    for i, config in enumerate(saved_configs[user_id], 1):
        text += (
            f"{i}. <b>{config['name']}</b>\n"
            f"   URL: <code>{config['stream_url'][:40]}...</code>\n"
            f"   Запуск: /run {config['name']}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("run"))
async def cmd_run(message: Message):
    """Запустити збережену конфігурацію"""
    user_id = message.from_user.id
    args = message.text.split()

    if len(args) != 2:
        await message.answer(
            "❌ Вкажіть назву конфігурації:\n"
            "Приклад: <code>/run webcam</code>",
            parse_mode="HTML"
        )
        return

    name = args[1]

    if user_id not in saved_configs:
        await message.answer("📭 У вас немає збережених конфігурацій")
        return

    for config in saved_configs[user_id]:
        if config['name'] == name:
            # Запускаємо трансляцію з збереженої конфігурації
            await start_stream(message, config['stream_url'], config['rtmp_url'], config['name'])
            return

    await message.answer(f"❌ Конфігурація '{name}' не знайдена")

@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    """Видалити збережену конфігурацію"""
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) != 2:
        await message.answer(
            "❌ Вкажіть назву конфігурації:\n"
            "Приклад: <code>/delete webcam</code>",
            parse_mode="HTML"
        )
        return
    
    name = args[1]
    
    if user_id not in saved_configs:
        await message.answer("📭 У вас немає збережених конфігурацій")
        return
    
    for i, config in enumerate(saved_configs[user_id]):
        if config['name'] == name:
            del saved_configs[user_id][i]
            save_configs()  # Зберігаємо зміни
            await message.answer(f"🗑 Конфігурацію '{name}' видалено")
            return

    await message.answer(f"❌ Конфігурація '{name}' не знайдена")

async def monitor_stream(user_id: int, stream_id: str, process: subprocess.Popen, chat_id: int):
    """Асинхронний моніторинг процесу трансляції"""
    while True:
        await asyncio.sleep(5)
        
        poll = process.poll()
        if poll is not None:
            # Процес завершився
            if user_id in active_streams and stream_id in active_streams[user_id]:
                config = active_streams[user_id][stream_id]['config']
                uptime = datetime.now() - config.start_time
                del active_streams[user_id][stream_id]
            else:
                uptime = None
            
            try:
                if poll == 0:
                    await bot.send_message(
                        chat_id,
                        f"✅ Трансляція {stream_id} успішно завершена\n"
                        f"Час роботи: {str(uptime).split('.')[0] if uptime else 'невідомо'}"
                    )
                else:
                    stderr_output = process.stderr.read()[:500] if process.stderr else "Немає інформації"
                    await bot.send_message(
                        chat_id,
                        f"⚠️ Трансляція {stream_id} завершилася з помилкою\n"
                        f"Код виходу: {poll}\n"
                        f"Час роботи: {str(uptime).split('.')[0] if uptime else 'невідомо'}\n\n"
                        f"Деталі:\n<code>{stderr_output}</code>",
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Помилка відправки повідомлення: {e}")
            
            break

async def on_shutdown():
    """Завершення всіх активних трансляцій при зупинці бота"""
    logger.info("Зупинка бота, завершення всіх трансляцій...")
    
    for user_id, streams in active_streams.items():
        for stream_id, stream_data in streams.items():
            process = stream_data['process']
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
    
    active_streams.clear()

async def main():
    """Головна функція запуску бота"""
    logger.info("Запуск Stream Bot...")

    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ Встановіть BOT_TOKEN в файлі .env!")
        return

    # Завантаження збережених конфігурацій
    load_configs()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await on_shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
