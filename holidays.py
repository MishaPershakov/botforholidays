import json
import random
import time
from datetime import datetime
from threading import Thread

import telebot
import pytz

# Импортируем настройки и праздники
import config
import holidays_data

# Создаем бота
bot = telebot.TeleBot(config.TOKEN)

# ============================================
# НАСТРОЙКА ЧАСОВОГО ПОЯСА (Москва)
# ============================================
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Файлы для хранения данных
SUBS_FILE = 'subs.json'           # личные подписки
GROUP_CHATS_FILE = 'group_chats.json'  # групповые чаты для рассылки

def get_current_time():
    """Возвращает текущее время в часовом поясе Москвы"""
    return datetime.now(MOSCOW_TZ)

# Вспомогательные функции
def get_weekday_name(date):
    """Название дня недели на русском"""
    days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return days[date.weekday()]

def is_weekend(date):
    """Проверка на выходной (сб/вс)"""
    return date.weekday() >= 5

def get_today_holiday():
    """Получаем праздник на сегодня по московскому времени"""
    now = get_current_time()
    date_key = now.strftime("%m-%d")
    
    holiday = holidays_data.HOLIDAYS.get(date_key)
    if not holiday:
        holiday = random.choice(holidays_data.FUNNY_HOLIDAYS)
    return holiday

# ==================== Работа с данными ====================

def load_json(filename, default=None):
    """Загружает данные из JSON файла"""
    if default is None:
        default = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(filename, data):
    """Сохраняет данные в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_subscribers():
    """Загружаем личных подписчиков"""
    return load_json(SUBS_FILE, {})

def save_subscribers(subs):
    """Сохраняем личных подписчиков"""
    save_json(SUBS_FILE, subs)

def load_group_chats():
    """Загружаем групповые чаты для рассылки"""
    return load_json(GROUP_CHATS_FILE, {})

def save_group_chats(chats):
    """Сохраняем групповые чаты"""
    save_json(GROUP_CHATS_FILE, chats)

# ==================== Обработчики команд ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_name = message.from_user.first_name
    chat_type = message.chat.type
    
    if chat_type == 'private':
        # Личный чат
        bot.reply_to(message,
            f"👋 Привет, {user_name}!\n\n"
            f"Я {config.BOT_NAME}.\n"
            "Каждый будний день в 7 утра по Москве присылаю праздник дня.\n\n"
            "/subscribe - подписаться лично\n"
            "/add_chat - добавить этот чат в рассылку (для групп)\n"
            "/remove_chat - удалить чат из рассылки\n"
            "/today - праздник сейчас\n"
            "/help - помощь")
    else:
        # Групповой чат
        bot.reply_to(message,
            f"👋 Привет, {user_name}!\n\n"
            "Я могу присылать праздники в этот чат каждый день в 7 утра.\n\n"
            "❗️ Чтобы я мог писать, сделайте меня администратором!\n\n"
            "/add_chat - добавить этот чат в рассылку\n"
            "/remove_chat - удалить из рассылки\n"
            "/today - праздник сейчас")

@bot.message_handler(commands=['subscribe'])
def subscribe_command(message):
    """Подписка для личных сообщений"""
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Эта команда работает только в личных сообщениях")
        return
    
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    now = get_current_time()
    
    subs = load_subscribers()
    subs[user_id] = {
        "name": user_name,
        "subscribed_at": now.strftime("%Y-%m-%d %H:%M")
    }
    save_subscribers(subs)
    
    bot.reply_to(message,
        "✅ Подписал!\n\n"
        "📅 Буду писать тебе лично:\n"
        f"• Пн-Пт в {config.MORNING_HOUR}:{config.MORNING_MINUTE:02d} по Москве\n"
        "• Сб-Вс отдыхаю")

@bot.message_handler(commands=['unsubscribe'])
def unsubscribe_command(message):
    """Отписка для личных сообщений"""
    if message.chat.type != 'private':
        bot.reply_to(message, "❌ Эта команда работает только в личных сообщениях")
        return
    
    user_id = str(message.from_user.id)
    
    subs = load_subscribers()
    if user_id in subs:
        del subs[user_id]
        save_subscribers(subs)
        bot.reply_to(message, "📭 Отписал. Захочешь вернуться - /subscribe")
    else:
        bot.reply_to(message, "Ты и так не подписан")

@bot.message_handler(commands=['add_chat'])
def add_chat_command(message):
    """Добавить групповой чат в рассылку"""
    chat_id = str(message.chat.id)
    chat_title = message.chat.title or f"Чат {chat_id}"
    chat_type = message.chat.type
    
    if chat_type == 'private':
        bot.reply_to(message, 
            "❌ Эта команда для групповых чатов!\n"
            "Если хочешь подписаться лично, используй /subscribe")
        return
    
    # Проверяем, является ли бот администратором
    try:
        bot.get_chat_administrators(chat_id)
    except:
        bot.reply_to(message, 
            "❌ Я не могу проверить права администратора!\n"
            "Сделайте меня администратором чата и попробуйте снова.")
        return
    
    chats = load_group_chats()
    chats[chat_id] = {
        "title": chat_title,
        "added_at": get_current_time().strftime("%Y-%m-%d %H:%M")
    }
    save_group_chats(chats)
    
    bot.reply_to(message,
        f"✅ Чат '{chat_title}' добавлен в рассылку!\n\n"
        f"📅 Буду писать сюда каждый будний день в {config.MORNING_HOUR}:{config.MORNING_MINUTE:02d} по Москве")

@bot.message_handler(commands=['remove_chat'])
def remove_chat_command(message):
    """Удалить групповой чат из рассылки"""
    chat_id = str(message.chat.id)
    chat_title = message.chat.title or f"Чат {chat_id}"
    
    chats = load_group_chats()
    if chat_id in chats:
        del chats[chat_id]
        save_group_chats(chats)
        bot.reply_to(message, f"📭 Чат '{chat_title}' удален из рассылки")
    else:
        bot.reply_to(message, "❌ Этого чата нет в рассылке")

@bot.message_handler(commands=['today'])
def today_command(message):
    """Показать праздник прямо сейчас"""
    user_name = message.from_user.first_name
    holiday = get_today_holiday()
    now = get_current_time()
    
    msg = (f"👋 {user_name}!\n"
           f"За бортом {now.strftime('%d.%m')} {get_weekday_name(now)}, "
           f"#праздникнасегодня *{holiday['name']}*\n\n"
           f"📝 {holiday['desc']}\n\n"
           f"Хорошего дня! 😊")
    
    bot.reply_to(message, msg, parse_mode='Markdown')


@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика бота"""
    subs = load_subscribers()
    chats = load_group_chats()
    now = get_current_time()
    
    stats_msg = (
        f"📊 *Статистика бота*\n\n"
        f"👤 Личных подписчиков: {len(subs)}\n"
        f"👥 Групповых чатов: {len(chats)}\n"
        f"📅 Праздников в базе: {len(holidays_data.HOLIDAYS)}\n"
        f"🕐 Время (Мск): {now.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"Рассылка: пн-пт в {config.MORNING_HOUR}:{config.MORNING_MINUTE:02d}"
    )
    
    bot.reply_to(message, stats_msg, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    """Помощь"""
    help_text = (
        "🌟 *Утренний Бот Праздников*\n\n"
        "*Личные команды:*\n"
        "/subscribe - подписаться лично\n"
        "/unsubscribe - отписаться\n\n"
        "*Групповые команды:*\n"
        "/add_chat - добавить чат в рассылку\n"
        "/remove_chat - удалить чат\n\n"
        "*Общие команды:*\n"
        "/today - праздник сейчас\n"
        "/stats - статистика\n\n"
        f"Рассылка: пн-пт {config.MORNING_HOUR}:{config.MORNING_MINUTE:02d} по Москве"
    )
    
    bot.reply_to(message, help_text, parse_mode='Markdown')

# ==================== Функция рассылки ====================

def morning_mailing():
    """Бесконечный цикл проверки времени и отправки"""
    while True:
        try:
            now = get_current_time()
            
            # Проверяем время
            if (now.hour == config.MORNING_HOUR and now.minute == config.MORNING_MINUTE):
                if config.SEND_ON_WEEKENDS or not is_weekend(now):
                    print(f"📨 Рассылка в {now.strftime('%H:%M')} по Москве")
                    
                    # Получаем праздник
                    holiday = get_today_holiday()
                    date_str = now.strftime("%d.%m")
                    weekday = get_weekday_name(now)
                    
                    # Формируем сообщение
                    msg = (f"👋 Доброе утро!\n"
                           f"За бортом {date_str} {weekday}, "
                           f"#праздникнасегодня *{holiday['name']}*\n\n"
                           f"📝 {holiday['desc']}\n\n"
                           f"Хорошего дня! 😊")
                    
                    # 1. Отправляем личным подписчикам
                    subs = load_subscribers()
                    for uid, udata in subs.items():
                        try:
                            personal_msg = (f"👋 Доброе утро, {udata['name']}!\n"
                                          f"За бортом {date_str} {weekday}, "
                                          f"#праздникнасегодня *{holiday['name']}*\n\n"
                                          f"📝 {holiday['desc']}\n\n"
                                          f"Хорошего дня! 😊")
                            bot.send_message(int(uid), personal_msg, parse_mode='Markdown')
                            print(f"✅ Личное: {uid}")
                            time.sleep(0.1)
                        except Exception as e:
                            print(f"❌ Ошибка личной отправки {uid}: {e}")
                    
                    # 2. Отправляем в групповые чаты
                    chats = load_group_chats()
                    for chat_id, chat_data in chats.items():
                        try:
                            bot.send_message(int(chat_id), msg, parse_mode='Markdown')
                            print(f"✅ Группа: {chat_data['title']}")
                            time.sleep(0.1)
                        except Exception as e:
                            print(f"❌ Ошибка отправки в группу {chat_id}: {e}")
                    
                    # Чтобы не повторять в ту же минуту
                    time.sleep(60)
            
            time.sleep(30)
            
        except Exception as e:
            print(f"Ошибка в рассылке: {e}")
            time.sleep(60)

# ==================== Запуск ====================

if __name__ == "__main__":
    print("\n" + "="*50)
    print(f"🌅 {config.BOT_NAME}")
    print("="*50)
    
    # Загружаем статистику
    subs = load_subscribers()
    chats = load_group_chats()
    current_time = get_current_time()
    
    print(f"📅 Праздников: {len(holidays_data.HOLIDAYS)}")
    print(f"👤 Личных подписчиков: {len(subs)}")
    print(f"👥 Групповых чатов: {len(chats)}")
    print(f"📨 Рассылка: пн-пт в {config.MORNING_HOUR}:{config.MORNING_MINUTE:02d}")
    print("="*50 + "\n")
    
    # Проверка токена
    if config.TOKEN == "7956422887:AAHm2b7p_y-MNwPj_23N6OPaUz_8Yb9QrOM":
        print("❌ ВНИМАНИЕ: в config.py указан токен-заглушка. Замените на свой!")
        exit()
    
    # Запускаем поток рассылки
    mailing_thread = Thread(target=morning_mailing, daemon=True)
    mailing_thread.start()
    
    print("✅ Бот запущен! Жми Ctrl+C для остановки.\n")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")