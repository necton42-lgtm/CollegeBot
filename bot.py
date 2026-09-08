import telebot
import requests
import os
import urllib3
import datetime
import json

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- ТВОИ ДАННЫЕ ---
TOKEN = '8382440830:AAEnLRLDwIH_Y6JlD5sMjVJgplnIkLqU6JM'
# Теперь это список! Добавляй сюда ID групп через запятую.
CHAT_IDS = [-1004414249637] 
ALLOWED_USERS = [5123128619]

bot = telebot.TeleBot(TOKEN)

session = requests.Session()
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, 'last_schedule.txt')
MSG_ID_FILE = os.path.join(BASE_DIR, 'last_message_ids.json') # Теперь JSON для нескольких чатов

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
            print(f"Ошибка при проверке {file_url}: {e}")
            
    return None, None

@bot.message_handler(commands=['ras', 'raspisanie', 'рас'])
@bot.message_handler(func=lambda message: message.text and 'расписание' in message.text.lower())
def handle_schedule_request(message):
    if message.from_user.id not in ALLOWED_USERS:
        return

    bot.send_chat_action(message.chat.id, 'typing')
    latest_url, date_str = find_schedule_by_date()
    
    if not latest_url:
        bot.reply_to(message, "❌ Актуальное расписание на ближайшие дни не найдено.")
        return

    last_sent_url = ""
    saved_msg_ids = {}

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            last_sent_url = f.read().strip()

    if os.path.exists(MSG_ID_FILE):
        with open(MSG_ID_FILE, 'r', encoding='utf-8') as f:
            try:
                saved_msg_ids = json.load(f)
            except json.JSONDecodeError:
                saved_msg_ids = {}

    # Скачиваем файл один раз для всех групп
    file_response = None

    for chat_id in CHAT_IDS:
        str_chat_id = str(chat_id)
        last_msg_id = saved_msg_ids.get(str_chat_id)
        
        # Логика тихой проверки: если ссылка та же самая и есть ID сообщения
        if latest_url == last_sent_url and last_msg_id:
            deleted = True
            try:
                # Тихая проверка через реакцию (бот должен иметь права на реакции в группе)
                bot.set_message_reaction(chat_id=chat_id, message_id=last_msg_id, reaction=[telebot.types.ReactionTypeEmoji('👍')])
                deleted = False
            except Exception:
                deleted = True

            if not deleted:
                if message.chat.id == chat_id or message.chat.type == 'private':
                    bot.reply_to(message, f"ℹ️ Расписание на {date_str} уже есть в группе {chat_id}. Нового пока нет.")
                continue # Переходим к следующей группе
            else:
                if message.chat.id == chat_id or message.chat.type == 'private':
                    bot.reply_to(message, f"🔄 В группе {chat_id} расписание было удалено. Отправляю заново...")

        # Если дошли сюда, значит надо отправлять. Скачиваем файл, если еще не скачали.
        if not file_response:
            try:
                file_response = session.get(latest_url, timeout=30)
                if file_response.status_code != 200:
                    bot.reply_to(message, f"❌ Ошибка скачивания с сайта (код {file_response.status_code}).")
                    return
                # Защита от мусора в 1 КБ
                if len(file_response.content) < 10000:
                    bot.reply_to(message, "⚠️ Сайт заблокировал скачивание (скачался пустой файл).")
                    return
            except Exception as e:
                bot.reply_to(message, f"❌ Ошибка сети: {e}")
                return

        # Отправка файла
        try:
            sent_msg = bot.send_document(
                chat_id=chat_id,
                document=(f"{date_str}.pdf", file_response.content),
                caption=f"📅 Расписание на {date_str}"
            )
            saved_msg_ids[str_chat_id] = sent_msg.message_id
            
            if message.chat.id == chat_id or message.chat.type == 'private':
                bot.reply_to(message, f"✅ Расписание на {date_str} успешно отправлено!")
                
        except Exception as e:
            if message.chat.id == chat_id or message.chat.type == 'private':
                bot.reply_to(message, f"❌ Ошибка при отправке: {e}")

    # Сохраняем актуальные данные после перебора всех чатов
    if file_response:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            f.write(latest_url)
        with open(MSG_ID_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved_msg_ids, f)

if __name__ == '__main__':
    print("🤖 Бот запущен (Мультичат + Защита от заглушек + Termux Ready)!")
    bot.infinity_polling()

