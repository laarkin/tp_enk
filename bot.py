import os
import sys
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hbold, hcode

# Определяем папку для данных (Railway volume)
if os.path.exists('/app/data'):
    DATA_DIR = '/app/data'
else:
    DATA_DIR = '.'

# Пути к файлам с данными
USER_ID_FILE = os.path.join(DATA_DIR, "user_id_map.txt")
POST_COUNTER_FILE = os.path.join(DATA_DIR, "post_number.txt")
ADMIN_MODE_FILE = os.path.join(DATA_DIR, "admin_mode.txt")

# Токен из переменных окружения
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

ADMINS = [972486843]  # Твой ID
CHANNEL_ID = -1003774797100  # ID канала

bot = Bot(token=TOKEN)
dp = Dispatcher()

FOOTER_TEXT = (
    "────────────\n"
    "📺 <a href='https://t.me/perehodniknaspletni'>Канал</a>\n"
    "✉️ <a href='https://t.me/enkspletni_bot'>Анонка</a>"
)

# ---------------- ХРАНИЛИЩЕ МЕДИА ГРУПП ----------------
media_groups = {}
user_messages = {}

# ---------------- Работа с ID пользователей ----------------
def load_user_id_map():
    if not os.path.exists(USER_ID_FILE):
        return {}
    mapping = {}
    with open(USER_ID_FILE, "r") as f:
        for line in f:
            if ':' in line:
                tid, uid = line.strip().split(":")
                mapping[int(tid)] = int(uid)
    return mapping

def save_user_id_map(mapping):
    with open(USER_ID_FILE, "w") as f:
        for tid, uid in mapping.items():
            f.write(f"{tid}:{uid}\n")

user_id_map = load_user_id_map()

def get_user_id_counter(telegram_id: int):
    """Возвращает ВНУТРЕННИЙ ID пользователя (1, 2, 3...)"""
    if telegram_id in user_id_map:
        return user_id_map[telegram_id]
    
    if user_id_map:
        next_id = max(user_id_map.values()) + 1
    else:
        next_id = 1
    
    user_id_map[telegram_id] = next_id
    save_user_id_map(user_id_map)
    return next_id

def get_telegram_id_by_counter(user_counter: int):
    """По ВНУТРЕННЕМУ ID (1, 2, 3...) возвращает Telegram ID"""
    for tid, uid in user_id_map.items():
        if uid == user_counter:
            return tid
    return None

def check_duplicate_ids():
    global user_id_map
    values = list(user_id_map.values())
    duplicates = set()
    
    for i, val1 in enumerate(values):
        for val2 in values[i+1:]:
            if val1 == val2:
                duplicates.add(val1)
    
    if duplicates:
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

# ---------------- РЕЖИМ ПРИНЯТИЯ ----------------
def is_admin_accepting() -> bool:
    if not os.path.exists(ADMIN_MODE_FILE):
        return True
    with open(ADMIN_MODE_FILE, "r") as f:
        return f.read().strip() == "on"

def set_admin_accepting(mode: bool):
    with open(ADMIN_MODE_FILE, "w") as f:
        f.write("on" if mode else "off")

# ---------------- КЛАВИАТУРЫ ----------------
def admin_keyboard(user_id_counter: int, post_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"approve:{user_id_counter}:{post_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{user_id_counter}:{post_id}")
        ]
    ])

def published_keyboard(message_id: int, footer_id: int = 0):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить пост из канала", callback_data=f"delete:{message_id}:{footer_id}")]
    ])

# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    
    welcome_text = (
        f"✨ {hbold('Привет, ' + user_name + '!')} ✨\n\n"
        f"🤫 Пиши сюда сплетни, а я анонимно отправлю их в канал\n\n"
        f"🔒 {hbold('Всё абсолютно анонимно')}\n"
        f"📝 Просто отправь мне текст, фото или видео\n\n"
        f"👇 Жду твои сообщения!"
    )
    
    await message.answer(welcome_text, parse_mode="HTML")
    # Регистрируем пользователя и получаем его внутренний ID
    get_user_id_counter(message.from_user.id)

# ---------------- HELP (ИСПРАВЛЕН) ----------------
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    if message.from_user.id in ADMINS:
        cmds = [
            "/stats 📊 - статистика",
            "/broadcast 📢 - рассылка",
            "/toggle_accept 🔄 - вкл/выкл прием",
            "/reply <ВНУТРЕННИЙ_ID> <текст> 💬 - ответ пользователю",
            "/list_users 📋 - список пользователей",
            "/check_ids ✅ - проверить ID",
            "/myid 🆔 - узнать свой ID",
            "/test_user <ВНУТРЕННИЙ_ID> 🧪 - тест отправки"
        ]
        await message.answer(
            "🔧 " + hbold("КОМАНДЫ АДМИНА") + "\n\n" + 
            "\n".join(cmds) + "\n\n"
            "💡 Внутренний ID = номер пользователя (1, 2, 3...)\n"
            "📌 Используй внутренний ID в командах /reply и /test_user",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"📱 {hbold('/start')} - начать\n"
            f"🆔 {hbold('/myid')} - узнать свой внутренний ID",
            parse_mode="HTML"
        )

# ---------------- REPLY (ИСПРАВЛЕН) ----------------
@dp.message(Command("reply"))
async def admin_reply(message: types.Message):
    """Ответ пользователю по ВНУТРЕННЕМУ ID"""
    
    if message.from_user.id not in ADMINS:
        return
    
    command_text = message.text or message.caption
    if not command_text:
        await message.answer("❌ Не могу найти команду")
        return
    
    try:
        parts = command_text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("❌ Формат: /reply <ВНУТРЕННИЙ_ID> <текст>")
            return
        
        user_counter = int(parts[1])  # Внутренний ID (1, 2, 3...)
        reply_text = parts[2]
        
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        return
    
    # Ищем пользователя по ВНУТРЕННЕМУ ID
    telegram_id = get_telegram_id_by_counter(user_counter)
    
    if not telegram_id:
        await message.answer(f"❌ Пользователь с внутренним ID {user_counter} не найден")
        return
    
    try:
        if message.photo:
            photo = message.photo[-1]
            await bot.send_photo(
                chat_id=telegram_id,
                photo=photo.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        elif message.video:
            await bot.send_video(
                chat_id=telegram_id,
                video=message.video.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        elif message.document:
            await bot.send_document(
                chat_id=telegram_id,
                document=message.document.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        elif message.voice:
            await bot.send_voice(
                chat_id=telegram_id,
                voice=message.voice.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        elif message.audio:
            await bot.send_audio(
                chat_id=telegram_id,
                audio=message.audio.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        elif message.animation:
            await bot.send_animation(
                chat_id=telegram_id,
                animation=message.animation.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Ответ отправлен пользователю #{user_counter}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

# ---------------- ТЕСТ ПОЛЬЗОВАТЕЛЯ (ИСПРАВЛЕН) ----------------
@dp.message(Command("test_user"))
async def test_user(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ Используйте: /test_user <ВНУТРЕННИЙ_ID>")
            return
        
        user_counter = int(args[1])  # Внутренний ID
        telegram_id = get_telegram_id_by_counter(user_counter)
        
        if not telegram_id:
            await message.answer(f"❌ Пользователь с внутренним ID {user_counter} не найден")
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
    
    await message.answer(
        f"📊 {hbold('СТАТИСТИКА')}\n"
        f"━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: {len(user_id_map)}\n"
        f"📝 Опубликовано: {posts}\n"
        f"━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

@dp.message(Command("check_ids"))
async def check_ids(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    global user_id_map
    user_id_map = check_duplicate_ids()
    await message.answer(f"✅ Проверка завершена")

# ---------------- СПИСОК ПОЛЬЗОВАТЕЛЕЙ (ИСПРАВЛЕН) ----------------
@dp.message(Command("list_users"))
async def list_users(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    
    if not user_id_map:
        await message.answer("❌ Нет пользователей")
        return
    
    text = f"📋 {hbold('СПИСОК ПОЛЬЗОВАТЕЛЕЙ')}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Внутр.ID | Telegram ID\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for tid, uid in sorted(user_id_map.items(), key=lambda x: x[1]):
        text += f"{uid:7} | {tid}\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👥 Всего: {len(user_id_map)} пользователей"
    
    await message.answer(text[:4000], parse_mode="HTML")

# ---------------- MYID (ИСПРАВЛЕН) ----------------
@dp.message(Command("myid"))
async def my_id(message: types.Message):
    user_counter = get_user_id_counter(message.from_user.id)  # Внутренний ID
    await message.answer(
        f"🆔 {hbold('Ваш внутренний ID:')} {hcode(str(user_counter))}\n"
        f"📱 Telegram ID: {hcode(str(message.from_user.id))}",
        parse_mode="HTML"
    )

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
    user_id_counter = get_user_id_counter(telegram_id)  # Внутренний ID
    post_id = get_next_post_id()
    
    user = first_msg.from_user
    username = f"@{user.username}" if user.username else "❌ Нет username"
    full_name = user.full_name or "Не указано"
    
    user_messages[user_id_counter] = {
        'type': 'media_group',
        'media_group_id': media_group_id,
        'messages': messages,
        'caption': first_msg.caption or '',
        'user_id_counter': user_id_counter,
        'post_id': post_id
    }
    
    # Отправляем админам
    for admin in ADMINS:
        try:
            # ИСПРАВЛЕНО: показываем ВНУТРЕННИЙ ID и TELEGRAM ID правильно
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
                f"└ 🖼 Медиа в альбоме: `{len(messages)}`\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(admin, text, parse_mode="Markdown")
            
            # Создаем медиа-группу для отправки
            media_group = []
            
            for i, msg in enumerate(messages):
                if msg.photo:
                    file_id = msg.photo[-1].file_id
                    if i == 0:
                        media_group.append(
                            types.InputMediaPhoto(
                                media=file_id,
                               
