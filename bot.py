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

USER_ID_FILE = "user_id_map.txt"
POST_COUNTER_FILE = "post_number.txt"
ADMIN_MODE_FILE = "admin_mode.txt"

FOOTER_TEXT = (
    "────────────\n"
    "📺 <a href='https://t.me/perehodniknaspletni'>Канал</a> |\n"
    "✉️ <a href='https://t.me/enkspletni_bot'>Анонка</a>"
)

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

def published_keyboard(message_id: int, footer_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить пост из канала", callback_data=f"delete:{message_id}:{footer_id}")]
    ])

# ---------------- START (ИСПРАВЛЕНО) ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    
    welcome_text = (
        f"✨ {hbold('Привет, ' + user_name + '!')} ✨\n\n"
        f"🤫 Пиши сюда сплетни, а я анонимно отправлю их в канал\n\n"
        f"🔒 {hbold('Всё абсолютно анонимно')} — можешь не переживать!\n"
        f"📝 Просто отправь мне текст, фото или видео\n\n"
        f"👇 Жду твои сообщения!"
    )
    
    await message.answer(
        welcome_text,
        parse_mode="HTML"
    )
    
    # Регистрируем пользователя
    get_user_id_counter(message.from_user.id)

# ---------------- HELP ----------------
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    if message.from_user.id in ADMINS:
        cmds = [
            "/stats 📊 - статистика",
            "/broadcast 📢 - рассылка",
            "/toggle_accept 🔄 - вкл/выкл прием от админа",
            "/reply <ID> <текст> 💬 - ответ пользователю (с фото/видео)",
            "/list_users 📋 - список пользователей",
            "/check_ids ✅ - проверить ID",
            "/myid 🆔 - узнать свой ID",
            "/test_user <ID> 🧪 - тест отправки"
        ]
        await message.answer("🔧 " + hbold("Команды админа:") + "\n\n" + "\n".join(cmds), parse_mode="HTML")
    else:
        await message.answer(
            f"📱 {hbold('/start')} - начать\n"
            f"🆔 {hbold('/myid')} - узнать свой ID",
            parse_mode="HTML"
        )

# ---------------- REPLY С ПОДДЕРЖКОЙ МЕДИА ----------------
@dp.message(Command("reply"))
async def admin_reply(message: types.Message):
    """Ответ пользователю с пересылкой фото/видео"""
    
    if message.from_user.id not in ADMINS:
        return
    
    # Получаем текст команды
    command_text = message.text or message.caption
    if not command_text:
        await message.answer("❌ Не могу найти команду")
        return
    
    # Парсим команду
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
    
    # Ищем пользователя
    telegram_id = get_telegram_id_by_counter(user_counter)
    
    if not telegram_id:
        await message.answer(f"❌ Пользователь с ID {user_counter} не найден")
        return
    
    # Отправляем ответ с медиа
    try:
        if message.photo:
            photo = message.photo[-1]
            await bot.send_photo(
                chat_id=telegram_id,
                photo=photo.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Фото отправлено #{user_counter}")
            
        elif message.video:
            await bot.send_video(
                chat_id=telegram_id,
                video=message.video.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Видео отправлено #{user_counter}")
            
        elif message.document:
            await bot.send_document(
                chat_id=telegram_id,
                document=message.document.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Документ отправлено #{user_counter}")
            
        elif message.voice:
            await bot.send_voice(
                chat_id=telegram_id,
                voice=message.voice.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Голосовое отправлено #{user_counter}")
            
        elif message.audio:
            await bot.send_audio(
                chat_id=telegram_id,
                audio=message.audio.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Аудио отправлено #{user_counter}")
            
        elif message.animation:
            await bot.send_animation(
                chat_id=telegram_id,
                animation=message.animation.file_id,
                caption=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ GIF отправлено #{user_counter}")
            
        else:
            await bot.send_message(
                chat_id=telegram_id,
                text=f"✉️ {hbold('Ответ от администратора:')}\n\n{reply_text}",
                parse_mode="HTML"
            )
            await message.answer(f"✅ Текст отправлен #{user_counter}")
        
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
    
    for tid, uid in sorted(user_id_map.items(), key=lambda x: x[1]):
        text += f"{uid:7} | {tid}\n"
    
    await message.answer(text[:4000], parse_mode="HTML")

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

# ---------------- ПОЛУЧЕНИЕ СООБЩЕНИЙ (ИСПРАВЛЕНО И ДОПОЛНЕНО) ----------------
user_messages = {}

@dp.message(F.text | F.photo | F.video | F.document | F.voice | F.audio | F.animation)
async def user_message(message: types.Message):
    """Обработчик сообщений от пользователей"""
    
    telegram_id = message.from_user.id
    
    # Админ с выключенным приемом - игнор
    if telegram_id in ADMINS and not is_admin_accepting():
        return
    
    # Игнорируем команды
    if message.text and message.text.startswith('/'):
        return
    
    user_id_counter = get_user_id_counter(telegram_id)
    post_id = get_next_post_id()
    
    # Сохраняем ПОЛНУЮ информацию о сообщении
    user_messages[user_id_counter] = {
        'chat_id': message.chat.id,
        'message_id': message.message_id,
        'content_type': message.content_type,
        'text': message.text or message.caption or '',
        'caption': message.caption or '',
        'media': None
    }
    
    # Для медиа сохраняем file_id
    if message.photo:
        user_messages[user_id_counter]['media'] = message.photo[-1].file_id
    elif message.video:
        user_messages[user_id_counter]['media'] = message.video.file_id
    elif message.document:
        user_messages[user_id_counter]['media'] = message.document.file_id
    elif message.voice:
        user_messages[user_id_counter]['media'] = message.voice.file_id
    elif message.audio:
        user_messages[user_id_counter]['media'] = message.audio.file_id
    elif message.animation:
        user_messages[user_id_counter]['media'] = message.animation.file_id
    
    # Получаем информацию о пользователе
    user = message.from_user
    username = f"@{user.username}" if user.username else "❌ Нет username"
    full_name = user.full_name or "Не указано"
    
    # Отправляем админам
    for admin in ADMINS:
        try:
            # Красивое оформление с полной информацией о пользователе
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
                f"└ 📝 Номер поста: `{post_id}`\n"
                "━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await bot.send_message(
                admin, 
                text, 
                parse_mode="Markdown"
            )
            
            # Пересылаем само сообщение
            await bot.copy_message(
                chat_id=admin,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=admin_keyboard(user_id_counter, post_id)
            )
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin}: {e}")
    
    await message.reply(f"✅ Ваше сообщение №{post_id} отправлено на модерацию!")

# ---------------- ПУБЛИКАЦИЯ (ИСПРАВЛЕНО) ----------------
@dp.callback_query(F.data.startswith("approve"))
async def approve(cb: types.CallbackQuery):
    try:
        data = cb.data.split(":")
        if len(data) < 3:
            await cb.answer("❌ Ошибка в данных")
            return
            
        user_id_counter = int(data[1])
        post_id = int(data[2])
    except (IndexError, ValueError):
        await cb.answer("❌ Ошибка в данных")
        return
    
    telegram_id = get_telegram_id_by_counter(user_id_counter)
    if not telegram_id:
        await cb.answer("❌ Пользователь не найден")
        return
    
    user_msg = user_messages.get(user_id_counter)
    if not user_msg:
        await cb.answer("❌ Сообщение не найдено")
        return
    
    try:
        # Футер который будет добавлен к посту
        footer = (
            "\n\n────────────\n"
            "📺 <a href='https://t.me/perehodniknaspletni'>Канал</a> |\n"
            "✉️ <a href='https://t.me/enkspletni_bot'>Анонка</a>"
        )
        
        if user_msg['content_type'] == 'text':
            # Для текста - добавляем футер к тексту
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
            await cb.answer("❌ Неподдерживаемый тип сообщения")
            return
        
        # Кнопка удаления для админа
        await cb.message.answer(
            f"✅ {hbold('Пост опубликован!')}\n\n"
            f"📝 Номер поста: {hcode(str(post_id))}\n"
            f"🆔 ID пользователя: {hcode(str(user_id_counter))}",
            reply_markup=published_keyboard(channel_msg.message_id, 0),
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                telegram_id,
                f"✅ {hbold('Ваше сообщение №' + str(post_id) + ' опубликовано в канале!')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Не удалось уведомить пользователя {telegram_id}: {e}")
        
        await cb.answer("✅ Опубликовано!")
        await cb.message.delete()
        
    except Exception as e:
        logging.error(f"Ошибка публикации: {e}")
        await cb.answer(f"❌ Ошибка при публикации: {str(e)[:50]}...")

# ---------------- ОТКЛОНЕНИЕ ----------------
@dp.callback_query(F.data.startswith("decline"))
async def decline(cb: types.CallbackQuery):
    try:
        data = cb.data.split(":")
        user_id_counter = int(data[1])
        post_id = int(data[2])
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
    
    await cb.answer("❌ Отклонено")
    await cb.message.delete()

# ---------------- УДАЛЕНИЕ ----------------
@dp.callback_query(F.data.startswith("delete"))
async def delete(cb: types.CallbackQuery):
    try:
        parts = cb.data.split(":")
        if len(parts) >= 2:
            channel_msg_id = int(parts[1])
            await bot.delete_message(CHANNEL_ID, channel_msg_id)
            
            if len(parts) >= 3 and parts[2] != '0':
                try:
                    await bot.delete_message(CHANNEL_ID, int(parts[2]))
                except:
                    pass
            
            await cb.answer("🗑 Удалено")
            
            # Обновляем сообщение админу
            if cb.message:
                try:
                    await cb.message.edit_text(
                        f"{cb.message.text}\n\n❌ {hbold('Пост удален из канала')}",
                        reply_markup=None,
                        parse_mode="HTML"
                    )
                except:
                    pass
        else:
            await cb.answer("❌ Ошибка в данных")
    except Exception as e:
        logging.error(f"Ошибка удаления: {e}")
        await cb.answer("❌ Ошибка при удалении")

# ---------------- ЗАПУСК ----------------
async def main():
    if not os.path.exists(ADMIN_MODE_FILE):
        set_admin_accepting(True)
    
    # Регистрируем админов
    for admin in ADMINS:
        if admin not in user_id_map:
            get_user_id_counter(admin)
    
    print("\n" + "="*50)
    print("🤖 БОТ ЗАПУЩЕН!")
    print("="*50)
    print(f"👤 Админы: {ADMINS}")
    print(f"📢 Канал: {CHANNEL_ID}")
    print(f"👥 Пользователей: {len(user_id_map)}")
    print("="*50 + "\n")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
