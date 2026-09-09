import telebot
import requests
import os
import urllib3
import datetime

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- НАСТРОЙКИ ---
TOKEN = '8382440830:AAEnLRLDwIH_Y6JlD5sMjVJgplnIkLqU6JM'
TOPIC_ID = 14679
CHAT_ID = -1002184995797
ALLOWED_USERS = [5123128619]

bot = telebot.TeleBot(TOKEN)

session = requests.Session()
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, 'last_schedule.txt')
MSG_ID_FILE = os.path.join(BASE_DIR, 'last_message_id.txt')

def find_schedule_by_date():
    today = datetime.date.today()
    search_offsets = [1, 2, 0, 3]
    
    for days_delta in search_offsets:
        target_date = today + datetime.timedelta(days=days_delta)
        date_str = target_date.strftime('%d.%m.%Y')
        file_url = f"https://kpgt-site.ru/upload/site_files/33/{date_str}.pdf"
        
        try:
            response = session.head(file_url, timeout=5)
            if response.status_code == 200:
                return file_url, date_str
        except Exception as e:
            print(f"Ошибка проверки {file_url}: {e}")
            
    return None, None

@bot.message_handler(commands=['ras', 'raspisanie', 'рас'])
@bot.message_handler(func=lambda message: message.text and 'расписание' in message.text.lower())
def handle_schedule_request(message):
    print(f"\n📩 Запрос от ID {message.from_user.id}")

    if message.from_user.id not in ALLOWED_USERS:
        print("⛔ Отказано: пользователь отсутствует в ALLOWED_USERS")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    latest_url, date_str = find_schedule_by_date()
    
    if not latest_url:
        print("❌ Файл расписания не найден.")
        bot.reply_to(message, "❌ Актуальное расписание на ближайшие дни не найдено.")
        return

    last_sent_url = ""
    last_msg_id = None

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            last_sent_url = f.read().strip()

    if os.path.exists(MSG_ID_FILE):
        with open(MSG_ID_FILE, 'r', encoding='utf-8') as f:
            try:
                last_msg_id = int(f.read().strip())
            except ValueError:
                last_msg_id = None

    # Если ссылка та же — проверяем, висит ли еще сообщение
    if latest_url == last_sent_url:
        if last_msg_id:
            try:
                # Пробуем тихо поставить реакцию на сообщение
                bot.set_message_reaction(chat_id=CHAT_ID, message_id=last_msg_id, reaction=[telebot.types.ReactionTypeEmoji('👍')])
                print("ℹ️ Расписание уже в группе.")
                bot.reply_to(message, f"ℹ️ Расписание на {date_str} уже есть в группе. Нового пока нет.")
                return
            except Exception:
                print("🔄 Сообщение удалено из группы, переотправляем...")
                bot.reply_to(message, f"🔄 Обнаружено, что расписание удалили из группы. Отправляю заново...")
        else:
            bot.reply_to(message, f"ℹ️ Расписание на {date_str} уже есть в группе. Нового пока нет.")
            return

    # Скачивание файла
    try:
        print("📥 Скачивание PDF...")
        file_response = session.get(latest_url, timeout=30)
        
        if file_response.status_code == 200:
            if len(file_response.content) < 10000:
                print("⚠️ Скачалась 1 КБ заглушка вместо PDF.")
                bot.reply_to(message, "⚠️ Сайт заблокировал скачивание (скачался пустой файл 1 КБ).")
                return

            print("📤 Отправка в Telegram...")
            sent_msg = bot.send_document(
                chat_id=CHAT_ID,
		message_thread_id=TOPIC_ID,
                document=(f"{date_str}.pdf", file_response.content),
                caption=f"📅 Расписание на {date_str}"
            )
            
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                f.write(latest_url)
            with open(MSG_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(str(sent_msg.message_id))

            print("✅ Готово!")
            bot.reply_to(message, f"✅ Расписание на {date_str} успешно отправлено!")
        else:
            bot.reply_to(message, f"❌ Ошибка скачивания с сайта (код {file_response.status_code}).")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        bot.reply_to(message, f"❌ Ошибка отправки: {e}")

if __name__ == '__main__':
    print("🤖 Бот запущен локально в Termux!")
    bot.infinity_polling()

