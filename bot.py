import os
import sys
import logging
import asyncio
import uuid
import time
import fcntl
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from aiogram.utils.markdown import hbold, hcode
from aiogram.exceptions import TelegramBadRequest, TelegramConflictError
from contextlib import contextmanager

# Определяем папку для данных (рядом со скриптом)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Пути к файлам с данными
USER_ID_FILE = os.path.join(DATA_DIR, "user_id_map.txt")
POST_COUNTER_FILE = os.path.join(DATA_DIR, "post_number.txt")
ADMIN_MODE_FILE = os.path.join(DATA_DIR, "admin_mode.txt")
REPLY_COUNTER_FILE = os.path.join(DATA_DIR, "reply_counter.txt")
LOCK_FILE = os.path.join(DATA_DIR, "bot.lock")  # Файл блокировки

# Токен из переменных окружения
TOKEN = "8333848471:AAGWllr1hLXTOD_rnwkJ3W34juYR56nQl0k"
if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

ADMINS = [6038185249]  # Твой ID
CHANNEL_ID = -1003712283690  # ID канала

# ---------------- ЗАЩИТА ОТ МНОЖЕСТВЕННЫХ ЗАПУСКОВ ----------------
def acquire_lock():
    """Создает файл блокировки для предотвращения множественных запусков"""
    try:
        # Пытаемся открыть файл для блокировки
        lock_file = open(LOCK_FILE, 'w')
        # Пробуем получить эксклюзивную блокировку
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Записываем PID процесса
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file
    except (IOError, OSError):
        # Не удалось получить блокировку - другой экземпляр уже запущен
        return None

def release_lock(lock_file):
    """Освобождает файл блокировки"""
    if lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            os.unlink(LOCK_FILE)
        except:
            pass

# ---------------- ИНИЦИАЛИЗАЦИЯ БОТА С ЗАЩИТОЙ ----------------
lock_file = acquire_lock()
if not lock_file:
    print("❌ ОШИБКА: Бот уже запущен в другом экземпляре!")
    print("   Если вы уверены, что это ошибка, удалите файл:", LOCK_FILE)
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

FOOTER_TEXT = (
    "────────────\n"
    "📺 <a href='https://t.me/perehodniknaspletni'>Канал</a>\n"
    "✉️ <a href='https://t.me/enkspletni_bot'>Анонка</a>"
)

# ---------------- ХРАНИЛИЩЕ МЕДИА ГРУПП И СООБЩЕНИЙ ----------------
media_groups = {}
user_messages = {}
channel_posts = {}

# ---------------- Работа с ID пользователей ----------------
def load_user_id_map():
    if not os.path.exists(USER_ID_FILE):
        return {}
    mapping = {}
    try:
        with open(USER_ID_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if ':' in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        tid, uid = parts
                        mapping[int(tid)] = int(uid)
    except Exception as e:
        logging.error(f"Ошибка загрузки user_id_map: {e}")
    return mapping

def save_user_id_map(mapping):
    try:
        with open(USER_ID_FILE, "w") as f:
            for tid, uid in mapping.items():
                f.write(f"{tid}:{uid}\n")
    except Exception as e:
        logging.error(f"Ошибка сохранения user_id_map: {e}")

user_id_map = load_user_id_map()

def get_next_user_counter():
    """Получить следующий свободный ID пользователя"""
    if not user_id_map:
        return 1
    used_ids = set(user_id_map.values())
    if not used_ids:
        return 1
    for i in range(1, max(used_ids) + 2):
        if i not in used_ids:
            return i
    return max(used_ids) + 1

def get_user_id_counter(telegram_id: int):
    """Получить внутренний ID пользователя, создать если нет"""
    check_duplicate_ids()
    
    if telegram_id in user_id_map:
        return user_id_map[telegram_id]
    
    next_id = get_next_user_counter()
    user_id_map[telegram_id] = next_id
    save_user_id_map(user_id_map)
    return next_id

def get_telegram_id_by_counter(user_counter: int):
    """Получить Telegram ID по внутреннему ID"""
    for tid, uid in user_id_map.items():
        if uid == user_counter:
            return tid
    return None

def check_duplicate_ids():
    """Проверка и исправление дубликатов ID"""
    global user_id_map
    
    value_to_keys = {}
    for tid, uid in user_id_map.items():
        if uid not in value_to_keys:
            value_to_keys[uid] = []
        value_to_keys[uid].append(tid)
    
    duplicates_found = False
    for uid, tids in value_to_keys.items():
        if len(tids) > 1:
            duplicates_found = True
            break
    
    if duplicates_found:
        new_mapping = {}
        next_id = 1
        for tid in user_id_map.keys():
            new_mapping[tid] = next_id
            next_id += 1
        user_id_map = new_mapping
        save_user_id_map(user_id_map)
    
    return user_id_map

user_id_map = check_duplicate_ids()

# ---------------- СЧЁТЧИК ПОСТОВ ----------------
def get_next_post_id():
    try:
        if not os.path.exists(POST_COUNTER_FILE):
            with open(POST_COUNTER_FILE, "w") as f:
                f.write("1")
            return 1
        with open(POST_COUNTER_FILE, "r") as f:
            try:
                num = int(f.read().strip())
            except:
                num = 1
        with open(POST_COUNTER_FILE, "w") as f:
            f.write(str(num + 1))
        return num
    except Exception as e:
        logging.error(f"Ошибка счетчика постов: {e}")
        return 1

# ---------------- СЧЁТЧИК ОТВЕТОВ ----------------
def get_next_reply_id():
    try:
        if not os.path.exists(REPLY_COUNTER_FILE):
            with open(REPLY_COUNTER_FILE, "w") as f:
                f.write("1")
            return 1
        with open(REPLY_COUNTER_FILE, "r") as f:
            try:
                num = int(f.read().strip())
            except:
                num = 1
        with open(REPLY_COUNTER_FILE, "w") as f:
            f.write(str(num + 1))
        return num
    except Exception as e:
        logging.error(f"Ошибка счетчика ответов: {e}")
        return 1

# ---------------- РЕЖИМ ПРИНЯТИЯ ----------------
def is_admin_accepting() -> bool:
    if not os.path.exists(ADMIN_MODE_FILE):
        return True
    try:
        with open(ADMIN_MODE_FILE, "r") as f:
            return f.read().strip() == "on"
    except:
        return True

def set_admin_accepting(mode: bool):
    try:
        with open(ADMIN_MODE_FILE, "w") as f:
            f.write("on" if mode else "off")
    except Exception as e:
        logging.error(f"Ошибка установки режима: {e}")

# ---------------- КЛАВИАТУРЫ ----------------
def admin_keyboard(user_id_counter: int, post_id: int, unique_id: str = None):
    """Клавиатура для админа с опциями публикации/отклонения"""
    data = f"approve:{user_id_counter}:{post_id}:{unique_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=data),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{user_id_counter}:{post_id}:{unique_id}")
        ]
    ])

def published_keyboard(post_group_id: str):
    """Клавиатура для удаления всего поста"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить пост из канала", callback_data=f"delete:{post_group_id}")]
    ])

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    
    welcome_text = (
        f"✨ {hbold('Привет, ' + user_name + '!')} ✨\n\n"
        f"🤫 Пиши сюда сплетни, а я анонимно отправлю их в канал\n\n"
        f"🔒 {hbold('Всё абсолютно анонимно')}\n"
        f"📝 Просто отправь мне текст, фото, видео или кружок\n\n"
        f"👇 Жду твои сообщения!"
    )
    
    await message.answer(welcome_text, parse_mode="HTML")
    get_user_id_counter(message.from_user.id)

# ---------------- HELP ----------------
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    if message.from_user.id in ADMINS:
        cmds = [
            "/stats 📊 - статистика",
            "/broadcast 📢 - рассылка",
            "/toggle_accept 🔄 - вкл/выкл прием от админа",
            "/reply <ID> <текст> 💬 - ответ пользователю (с фото/видео/кружком)",
            "/list_users 📋 - список пользователей",
            "/check_ids ✅ - проверить ID",
            "/myid 🆔 - узнать свой ID",
            "/test_user <ID> 🧪 - тест отправки",
            "/help 🆘 - это сообщение"
        ]
        help_text = "🔧 " + hbold("Команды админа:") + "\n\n" + "\n".join(f"• {cmd}" for cmd in cmds)
        await message.answer(help_text, parse_mode="HTML")
    else:
        help_text = (
            f"📱 {hbold('/start')} - начать\n"
            f"🆔 {hbold('/myid')} - узнать свой ID\n"
            f"❓ {hbold('/help')} - помощь"
        )
        await message.answer(help_text, parse_mode="HTML")

# ---------------- REPLY С ПОДДЕРЖКОЙ ВСЕХ ТИПОВ МЕДИА ----------------
@dp.message(Command("reply"))
async def admin_reply(message: types.Message):
    """Ответ пользователю с пересылкой любого типа медиа"""
    
    if message.from_user.id not in ADMINS:
        return
    
    command_text = message.text or message.caption
    if not command_text:
        await message.answer("❌ Не могу найти команду")
        return
    
    try:
        parts = command_text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("❌ Формат: /reply <ID> <текст>")
            return
        
        user_counter = int(parts[1])
        reply_text = parts[2]
        
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        return
    
    telegram_id = get_telegram_id_by_counter(user_counter)
    
    if not telegram_id:
        available_ids = sorted(user_id_map.values())
        ids_text = ", ".join(str(uid) for uid in available_ids[:20])
        if len(available_ids) > 20:
            ids_text += f"... и ещё {len(available_ids) - 20}"
        
        await message.answer(
            f"❌ Пользователь с ID {user_counter} не найден\n\n"
            f"📋 Доступные ID: {ids_text}",
            parse_mode="HTML"
        )
        return
    
    reply_id = get_next_reply_id()
    
    try:
        reply_header = f"✉️ {hbold('Ответ от администратора #' + str(reply_id) + ':')}\n\n"
        
        if message.photo:
            photo = message.photo[-1]
            await bot.send_photo(
                chat_id=telegram_id,
                photo=photo.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        elif message.video:
            await bot.send_video(
                chat_id=telegram_id,
                video=message.video.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        elif message.video_note:
            await bot.send_video_note(
                chat_id=telegram_id,
                video_note=message.video_note.file_id
            )
            if reply_text:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"{reply_header}{reply_text}",
                    parse_mode="HTML"
                )
        elif message.document:
            await bot.send_document(
                chat_id=telegram_id,
                document=message.document.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        elif message.voice:
            await bot.send_voice(
                chat_id=telegram_id,
                voice=message.voice.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        elif message.audio:
            await bot.send_audio(
                chat_id=telegram_id,
                audio=message.audio.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        elif message.animation:
            await bot.send_animation(
                chat_id=telegram_id,
                animation=message.animation.file_id,
                caption=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text=f"{reply_header}{reply_text}",
                parse_mode="HTML"
            )
        
        await message.answer(f"✅ Ответ #{reply_id} отправлен пользователю #{user_counter}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

# ---------------- ТЕСТ ПОЛЬЗОВАТЕЛЯ ----------------
@dp.message(Command("test_user"))
async def test_user(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Используйте: /test_user <ID>")
            return
        
        user_counter = int(args[1])
        telegram_id = get_telegram_id_by_counter(user_counter)
        
        if not telegram_id:
            await message.answer(f"❌ Пользователь с ID {user_counter} не найден")
            return
        
        await bot.send_message(
            telegram_id,
            f"🧪 {hbold('Тестовое сообщение от администратора')}\n\n"
            f"Если вы это видите - отправка работает! ✅",
            parse_mode="HTML"
        )
        
        await message.answer(f"✅ Тест отправлен пользователю #{user_counter}")
        
    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ---------------- СТАТИСТИКА ----------------
@dp.message(Command("stats"))
async def stats(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    posts = 0
    if os.path.exists(POST_COUNTER_FILE):
        with open(POST_COUNTER_FILE, "r") as f:
            try:
                posts = int(f.read().strip()) - 1
            except:
                posts = 0
    
    replies = 0
    if os.path.exists(REPLY_COUNTER_FILE):
        with open(REPLY_COUNTER_FILE, "r") as f:
            try:
                replies = int(f.read().strip()) - 1
            except:
                replies = 0
    
    await message.answer(
        f"📊 {hbold('СТАТИСТИКА')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: {len(user_id_map)}\n"
        f"📝 Опубликовано: {posts}\n"
        f"💬 Ответов: {replies}\n"
        f"━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

@dp.message(Command("check_ids"))
async def check_ids(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    global user_id_map
    old_count = len(user_id_map)
    user_id_map = check_duplicate_ids()
    new_count = len(user_id_map)
    
    await message.answer(
        f"✅ Проверка завершена\n"
        f"Пользователей: {new_count}",
        parse_mode="HTML"
    )

@dp.message(Command("list_users"))
async def list_users(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    if not user_id_map:
        await message.answer("❌ Нет пользователей")
        return
    
    text = f"📋 {hbold('СПИСОК ПОЛЬЗОВАТЕЛЕЙ')}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Внутр.ID | Telegram ID\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    
    sorted_users = sorted(user_id_map.items(), key=lambda x: x[1])
    for tid, uid in sorted_users:
        text += f"{uid:7} | {tid}\n"
        if len(text) > 3500:
            text += "\n... и ещё пользователи"
            break
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("myid"))
async def my_id(message: types.Message):
    user_counter = get_user_id_counter(message.from_user.id)
    await message.answer(f"🆔 {hbold('Ваш внутренний ID:')} {hcode(str(user_counter))}", parse_mode="HTML")

@dp.message(Command("toggle_accept"))
async def toggle_accept(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    new_mode = not is_admin_accepting()
    set_admin_accepting(new_mode)
    await message.answer(
        f"🔄 {hbold('Режим приема от админа')}\n"
        f"{'✅ ВКЛЮЧЕН' if new_mode else '❌ ВЫКЛЮЧЕН'}",
        parse_mode="HTML"
    )

@dp.message(Command("broadcast"))
async def broadcast(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение для рассылки")
        return
    
    users = list(user_id_map.keys())
    if not users:
        await message.answer("❌ Нет пользователей")
        return
    
    status_msg = await message.answer("📤 Начинаю рассылку...")
    success = 0
    failed = 0
    
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 {hbold('Сообщение от администратора:')}", parse_mode="HTML")
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id
            )
            success += 1
        except Exception as e:
            failed += 1
            logging.error(f"Ошибка рассылки пользователю {uid}: {e}")
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(
        f"✅ {hbold('Рассылка завершена!')}\n\n"
        f"📊 Статистика:\n"
        f"✓ Успешно: {success}\n"
        f"✗ Ошибок: {failed}\n"
        f"👥 Всего: {len(users)}",
        parse_mode="HTML"
    )

# ---------------- ОБРАБОТКА МЕДИА ГРУПП (АЛЬБОМОВ) ----------------
@dp.message(F.media_group_id)
async def handle_media_group(message: types.Message):
    """Обработка альбомов (несколько фото/видео)"""
    
    telegram_id = message.from_user.id
    
    if telegram_id in ADMINS and not is_admin_accepting():
        return
    
    media_group_id = message.media_group_id
    
    if media_group_id not in media_groups:
        media_groups[media_group_id] = {
            'messages': [],
            'timer': None,
            'user_id': telegram_id,
            'first_message': message
        }
    
    media_groups[media_group_id]['messages'].append(message)
    
    if media_groups[media_group_id]['timer']:
        media_groups[media_group_id]['timer'].cancel()
    
    loop = asyncio.get_event_loop()
    timer = loop.call_later(1.0, lambda: asyncio.create_task(process_media_group(media_group_id)))
    media_groups[media_group_id]['timer'] = timer

async def process_media_group(media_group_id: str):
    """Обработка собранного альбома"""
    
    group_data = media_groups.get(media_group_id)
    if not group_data:
        return
    
    messages = group_data['messages']
    first_msg = group_data['first_message']
    
    messages.sort(key=lambda x: x.date)
    
    telegram_id = group_data['user_id']
    user_id_counter = get_user_id_counter(telegram_id)
    post_id = get_next_post_id()
    unique_id = str(uuid.uuid4())
    
    user = first_msg.from_user
    username = f"@{user.username}" if user.username else "❌ Нет username"
    full_name = user.full_name or "Не указано"
    
    user_messages[unique_id] = {
        'type': 'media_group',
        'media_group_id': media_group_id,
        'messages': messages,
        'caption': first_msg.caption or '',
        'user_id_counter': user_id_counter,
        'post_id': post_id,
        'telegram_id': telegram_id,
        'unique_id': unique_id
    }
    
    for admin in ADMINS:
        try:
            text = (
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "📨 **ПРИШЛО АНОНИМНОЕ СООБЩЕНИЕ (АЛЬБОМ)**\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                "👤 **ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:**\n"
                f"├ 🆔 Внутренний ID: `{user_id_counter}`\n"
                f"├ 📱 Telegram ID: `{telegram_id}`\n"
                f"├ 👤 Имя: `{full_name}`\n"
                f"└ 🔗 Username: {username}\n\n"
                
                "📬 **ИНФОРМАЦИЯ О ПОСТЕ:**\n"
                f"├ 📝 Номер поста: `{post_id}`\n"
                f"├ 🆔 Уникальный ID: `{unique_id[:8]}...`\n"
                f"└ 🖼 Медиа в альбоме: `{len(messages)}`\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(admin, text, parse_mode="Markdown")
            
            media_group = []
            
            for i, msg in enumerate(messages):
                if msg.photo:
                    file_id = msg.photo[-1].file_id
                    if i == 0:
                        media_group.append(
                            InputMediaPhoto(
                                media=file_id,
                                caption=first_msg.caption or f"📸 Альбом | Пост #{post_id}",
                                parse_mode="HTML"
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaPhoto(
                                media=file_id
                            )
                        )
                elif msg.video:
                    file_id = msg.video.file_id
                    if i == 0:
                        media_group.append(
                            InputMediaVideo(
                                media=file_id,
                                caption=first_msg.caption or f"🎬 Альбом | Пост #{post_id}",
                                parse_mode="HTML"
                            )
                        )
                    else:
                        media_group.append(
                            InputMediaVideo(
                                media=file_id
                            )
                        )
            
            if media_group:
                await bot.send_media_group(admin, media_group)
            
            await bot.send_message(
                admin,
                f"🆔 ID пользователя: `{user_id_counter}` | Пост №`{post_id}` | Уникальный ID: `{unique_id[:8]}`",
                reply_markup=admin_keyboard(user_id_counter, post_id, unique_id),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logging.error(f"Ошибка отправки альбома админу {admin}: {e}")
    
    await first_msg.reply(f"✅ Ваш альбом №{post_id} отправлен на модерацию!")
    del media_groups[media_group_id]

# ---------------- ОБРАБОТКА ВСЕХ ТИПОВ СООБЩЕНИЙ ----------------
@dp.message(F.text | F.photo | F.video | F.video_note | F.document | F.voice | F.audio | F.animation)
async def user_message(message: types.Message):
    """Обработчик одиночных сообщений от пользователей"""
    
    if message.media_group_id:
        return
    
    telegram_id = message.from_user.id
    
    if telegram_id in ADMINS and not is_admin_accepting():
        return
    
    if message.text and message.text.startswith('/'):
        return
    
    user_id_counter = get_user_id_counter(telegram_id)
    post_id = get_next_post_id()
    unique_id = str(uuid.uuid4())
    
    user_messages[unique_id] = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'text': message.text or message.caption or '',
        'caption': message.caption or '',
        'user_id_counter': user_id_counter,
        'post_id': post_id,
        'telegram_id': telegram_id,
        'unique_id': unique_id
    }
    
    if message.photo:
        user_messages[unique_id]['media'] = message.photo[-1].file_id
    elif message.video:
        user_messages[unique_id]['media'] = message.video.file_id
    elif message.video_note:
        user_messages[unique_id]['media'] = message.video_note.file_id
    elif message.document:
        user_messages[unique_id]['media'] = message.document.file_id
    elif message.voice:
        user_messages[unique_id]['media'] = message.voice.file_id
    elif message.audio:
        user_messages[unique_id]['media'] = message.audio.file_id
    elif message.animation:
        user_messages[unique_id]['media'] = message.animation.file_id
    
    user = message.from_user
    username = f"@{user.username}" if user.username else "❌ Нет username"
    full_name = user.full_name or "Не указано"
    
    for admin in ADMINS:
        try:
            text = (
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "📨 **ПРИШЛО АНОНИМНОЕ СООБЩЕНИЕ**\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                "👤 **ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:**\n"
                f"├ 🆔 Внутренний ID: `{user_id_counter}`\n"
                f"├ 📱 Telegram ID: `{telegram_id}`\n"
                f"├ 👤 Имя: `{full_name}`\n"
                f"└ 🔗 Username: {username}\n\n"
                
                "📬 **ИНФОРМАЦИЯ О ПОСТЕ:**\n"
                f"├ 📝 Номер поста: `{post_id}`\n"
                f"├ 🆔 Уникальный ID: `{unique_id[:8]}...`\n"
                f"└ 📎 Тип: `{message.content_type}`\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(admin, text, parse_mode="Markdown")
            
            await bot.copy_message(
                chat_id=admin,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=admin_keyboard(user_id_counter, post_id, unique_id)
            )
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin}: {e}")
    
    await message.reply(f"✅ Ваше сообщение №{post_id} отправлено на модерацию!")

# ---------------- ПУБЛИКАЦИЯ С ПОДДЕРЖКОЙ АЛЬБОМОВ ----------------
@dp.callback_query(F.data.startswith("approve"))
async def approve(cb: types.CallbackQuery):
    try:
        data = cb.data.split(":")
        if len(data) < 4:
            await cb.answer("❌ Ошибка в данных")
            return
            
        user_id_counter = int(data[1])
        post_id = int(data[2])
        unique_id = data[3]
    except (IndexError, ValueError):
        await cb.answer("❌ Ошибка в данных")
        return
    
    telegram_id = get_telegram_id_by_counter(user_id_counter)
    if not telegram_id:
        await cb.answer("❌ Пользователь не найден")
        return
    
    user_msg = user_messages.get(unique_id)
    if not user_msg:
        await cb.answer("❌ Сообщение не найдено")
        return
    
    try:
        post_group_id = str(uuid.uuid4())
        channel_message_ids = []
        
        # ПУБЛИКАЦИЯ АЛЬБОМА
        if user_msg.get('type') == 'media_group':
            messages = user_msg['messages']
            messages.sort(key=lambda x: x.date)
            
            media_group = []
            video_notes = []
            
            # Разделяем кружочки и остальные медиа
            for msg in messages:
                if msg.video_note:
                    video_notes.append(msg)
                elif msg.photo or msg.video:
                    if msg.photo:
                        file_id = msg.photo[-1].file_id
                        if not media_group:
                            caption = msg.caption or ""
                            caption += f"\n\n{FOOTER_TEXT}"
                            media_group.append(
                                InputMediaPhoto(
                                    media=file_id,
                                    caption=caption,
                                    parse_mode="HTML"
                                )
                            )
                        else:
                            media_group.append(
                                InputMediaPhoto(
                                    media=file_id
                                )
                            )
                    elif msg.video:
                        file_id = msg.video.file_id
                        if not media_group:
                            caption = msg.caption or ""
                            caption += f"\n\n{FOOTER_TEXT}"
                            media_group.append(
                                InputMediaVideo(
                                    media=file_id,
                                    caption=caption,
                                    parse_mode="HTML"
                                )
                            )
                        else:
                            media_group.append(
                                InputMediaVideo(
                                    media=file_id
                                )
                            )
            
            # Отправляем кружочки
            for vn in video_notes:
                vn_msg = await bot.send_video_note(
                    chat_id=CHANNEL_ID,
                    video_note=vn.video_note.file_id
                )
                channel_message_ids.append(vn_msg.message_id)
            
            # Отправляем медиа-группу
            if media_group:
                channel_msgs = await bot.send_media_group(CHANNEL_ID, media_group)
                channel_message_ids.extend([msg.message_id for msg in channel_msgs])
            
            # Сохраняем информацию о посте
            if channel_message_ids:
                channel_posts[post_group_id] = {
                    'message_ids': channel_message_ids,
                    'user_counter': user_id_counter,
                    'post_id': post_id,
                    'unique_id': unique_id
                }
            
            await cb.message.answer(
                f"✅ {hbold('Альбом опубликован!')}\n\n"
                f"📝 Номер поста: {hcode(str(post_id))}\n"
                f"🆔 ID пользователя: {hcode(str(user_id_counter))}\n"
                f"🖼 Медиа в посте: {len(channel_message_ids)}",
                reply_markup=published_keyboard(post_group_id),
                parse_mode="HTML"
            )
        
        # ПУБЛИКАЦИЯ ОДИНОЧНОГО СООБЩЕНИЯ
        else:
            footer = f"\n\n{FOOTER_TEXT}"
            
            if user_msg['content_type'] == 'video_note':
                channel_msg = await bot.send_video_note(
                    chat_id=CHANNEL_ID,
                    video_note=user_msg['media']
                )
                channel_message_ids.append(channel_msg.message_id)
                
                if user_msg['caption']:
                    caption_msg = await bot.send_message(
                        CHANNEL_ID,
                        user_msg['caption'] + footer,
                        parse_mode="HTML"
                    )
                    channel_message_ids.append(caption_msg.message_id)
            else:
                if user_msg['content_type'] == 'text':
                    channel_msg = await bot.send_message(
                        CHANNEL_ID,
                        user_msg['text'] + footer,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                elif user_msg['content_type'] == 'photo':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif user_msg['content_type'] == 'video':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_video(
                        chat_id=CHANNEL_ID,
                        video=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif user_msg['content_type'] == 'document':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_document(
                        chat_id=CHANNEL_ID,
                        document=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif user_msg['content_type'] == 'voice':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_voice(
                        chat_id=CHANNEL_ID,
                        voice=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif user_msg['content_type'] == 'audio':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_audio(
                        chat_id=CHANNEL_ID,
                        audio=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                elif user_msg['content_type'] == 'animation':
                    caption = user_msg['caption'] or ""
                    caption += footer
                    channel_msg = await bot.send_animation(
                        chat_id=CHANNEL_ID,
                        animation=user_msg['media'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                else:
                    await cb.answer("❌ Неподдерживаемый тип")
                    return
                
                channel_message_ids.append(channel_msg.message_id)
            
            if channel_message_ids:
                channel_posts[post_group_id] = {
                    'message_ids': channel_message_ids,
                    'user_counter': user_id_counter,
                    'post_id': post_id,
                    'unique_id': unique_id
                }
            
            await cb.message.answer(
                f"✅ {hbold('Пост опубликован!')}\n\n"
                f"📝 Номер поста: {hcode(str(post_id))}\n"
                f"🆔 ID пользователя: {hcode(str(user_id_counter))}",
                reply_markup=published_keyboard(post_group_id),
                parse_mode="HTML"
            )
        
        if unique_id in user_messages:
            del user_messages[unique_id]
        
        try:
            await bot.send_message(
                telegram_id,
                f"✅ {hbold('Ваше сообщение №' + str(post_id) + ' опубликовано в канале!')}",
                parse_mode="HTML"
            )
        except:
            pass
        
        await cb.answer("✅ Опубликовано!")
        await cb.message.delete()
        
    except Exception as e:
        logging.error(f"Ошибка публикации: {e}")
        await cb.answer(f"❌ Ошибка: {str(e)[:50]}...")

# ---------------- ОТКЛОНЕНИЕ ----------------
@dp.callback_query(F.data.startswith("decline"))
async def decline(cb: types.CallbackQuery):
    try:
        data = cb.data.split(":")
        if len(data) < 4:
            await cb.answer("❌ Ошибка в данных")
            return
            
        user_id_counter = int(data[1])
        post_id = int(data[2])
        unique_id = data[3]
    except (IndexError, ValueError):
        await cb.answer("❌ Ошибка в данных")
        return
    
    telegram_id = get_telegram_id_by_counter(user_id_counter)
    if telegram_id:
        try:
            await bot.send_message(
                telegram_id,
                f"❌ {hbold('Ваше сообщение №' + str(post_id) + ' отклонено модератором')}",
                parse_mode="HTML"
            )
        except:
            pass
    
    if unique_id in user_messages:
        del user_messages[unique_id]
    
    await cb.answer("❌ Отклонено")
    await cb.message.delete()

# ---------------- УДАЛЕНИЕ ВСЕГО ПОСТА ----------------
@dp.callback_query(F.data.startswith("delete"))
async def delete_post(cb: types.CallbackQuery):
    """Удаление всего поста из канала"""
    try:
        parts = cb.data.split(":")
        if len(parts) < 2:
            await cb.answer("❌ Ошибка в данных")
            return
        
        post_group_id = parts[1]
        
        if post_group_id not in channel_posts:
            await cb.answer("❌ Пост не найден")
            return
        
        post_data = channel_posts[post_group_id]
        message_ids = post_data.get('message_ids', [])
        
        deleted_count = 0
        for msg_id in message_ids:
            try:
                await bot.delete_message(CHANNEL_ID, msg_id)
                deleted_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.error(f"Ошибка удаления сообщения {msg_id}: {e}")
        
        del channel_posts[post_group_id]
        
        await cb.answer(f"🗑 Удалено {deleted_count} сообщений")
        
        if cb.message:
            try:
                await cb.message.edit_text(
                    f"{cb.message.text}\n\n❌ {hbold('Пост удален из канала')} (удалено {deleted_count} сообщений)",
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except:
                pass
                
    except Exception as e:
        logging.error(f"Ошибка удаления: {e}")
        await cb.answer("❌ Ошибка при удалении")

# ---------------- ПЕРИОДИЧЕСКАЯ ОЧИСТКА СТАРЫХ СООБЩЕНИЙ ----------------
async def cleanup_old_messages():
    """Очистка старых сообщений из хранилища"""
    while True:
        await asyncio.sleep(24 * 60 * 60)
        
        if len(user_messages) > 100:
            keys_to_remove = list(user_messages.keys())[:-100]
            for key in keys_to_remove:
                del user_messages[key]
        
        logging.info(f"Очистка хранилища: {len(user_messages)} сообщений, {len(channel_posts)} постов")

# ---------------- ЗАПУСК ----------------
async def main():
    try:
        if not os.path.exists(ADMIN_MODE_FILE):
            set_admin_accepting(True)
        
        for admin in ADMINS:
            if admin not in user_id_map:
                get_user_id_counter(admin)
        
        asyncio.create_task(cleanup_old_messages())
        
        print("\n" + "="*50)
        print("🤖 БОТ ЗАПУЩЕН!")
        print("="*50)
        print(f"👤 Админы: {ADMINS}")
        print(f"📢 Канал: {CHANNEL_ID}")
        print(f"👥 Пользователей: {len(user_id_map)}")
        print(f"📁 Данные: {DATA_DIR}")
        print(f"🔒 Блокировка: {LOCK_FILE}")
        print("="*50 + "\n")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
    finally:
        # Освобождаем блокировку при завершении
        release_lock(lock_file)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
        release_lock(lock_file)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        release_lock(lock_file)
