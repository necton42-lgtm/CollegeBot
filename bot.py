import telebot
import requests
import os
import urllib3
import datetime

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- ТВОИ ДАННЫЕ ---
TOKEN = '8382440830:AAEnLRLDwIH_Y6JlD5sMjVJgplnIkLqU6JM'
CHAT_ID = '-1004414249637' # Убедись, что ID группы точный
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
    print(f"\n📩 Команда от ID {message.from_user.id} в чате {message.chat.id}")

    if message.from_user.id not in ALLOWED_USERS:
        print(f"⛔ Отказано: ID {message.from_user.id} нет в ALLOWED_USERS")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    latest_url, date_str = find_schedule_by_date()
    
    if not latest_url:
        print("❌ Файл расписания на сайте не найден.")
        bot.reply_to(message, "❌ Актуальное расписание на ближайшие дни не найдено.")
        return

    print(f"🔗 Найдена ссылка: {latest_url}")

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

    # Если ссылка совпадает — проверяем, существует ли еще сообщение в группе
    if latest_url == last_sent_url and last_msg_id:
        deleted = True
        try:
            # Тихая проверка через попытку поставить реакцию
            bot.set_message_reaction(chat_id=CHAT_ID, message_id=last_msg_id, reaction=[telebot.types.ReactionTypeEmoji('👍')])
            deleted = False
        except Exception as e:
            print(f"Сообщение {last_msg_id} удалено или недоступно: {e}")
            deleted = True

        if not deleted:
            print("ℹ️ Файл уже в группе и не был удален.")
            bot.reply_to(message, f"ℹ️ Расписание на {date_str} уже есть в группе. Нового пока нет.")
            return
        else:
            print("🔄 Сообщение с расписанием было удалено. Скачиваем заново...")
            bot.reply_to(message, f"🔄 Обнаружено, что расписание удалили из группы. Отправляю заново...")

    # Скачивание файла
    try:
        print("📥 Скачиваю PDF с сайта...")
        file_response = session.get(latest_url, timeout=30)
        
        if file_response.status_code == 200:
            # Зашита от 1 КБ мусора
            if len(file_response.content) < 10000:
                print("⚠️ Сайт вернул пустой файл (1 КБ заглушка от блокировки).")
                bot.reply_to(message, "⚠️ Сайт заблокировал скачивание (скачался пустой файл 1 КБ).")
                return

            print("📤 Отправляю PDF в Телеграм...")
            sent_msg = bot.send_document(
                chat_id=CHAT_ID,
                document=(f"{date_str}.pdf", file_response.content),
                caption=f"📅 Расписание на {date_str}"
            )
            
            # Сохраняем историю
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                f.write(latest_url)
            with open(MSG_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(str(sent_msg.message_id))

            print("✅ Успешно отправлено!")
            bot.reply_to(message, f"✅ Расписание на {date_str} успешно отправлено!")
        else:
            print(f"❌ Код ответа сайта: {file_response.status_code}")
            bot.reply_to(message, f"❌ Ошибка скачивания с сайта (код {file_response.status_code}).")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        bot.reply_to(message, f"❌ Ошибка отправки: {e}")

if __name__ == '__main__':
    print("🤖 Бот запущен (Режим одной группы + Отладка в консоли)!")
    bot.infinity_polling()

