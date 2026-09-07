import telebot
import requests
import os
import urllib3
import datetime
import time
import threading

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- ТВОИ ДАННЫЕ ---
TOKEN = '8382440830:AAEnLRLDwIH_Y6JlD5sMjVJgplnIkLqU6JM'
CHAT_ID = -1004414249637  
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
            print(f"Ошибка при проверке {file_url}: {e}")
            
    return None, None

# Функция автоматической проверки расписания в фоне каждые 30 минут
def background_schedule_checker():
    print("🔄 Фоновый процесс проверки расписания запущен.")
    while True:
        try:
            latest_url, date_str = find_schedule_by_date()
            if latest_url:
                last_sent_url = ""
                if os.path.exists(MEMORY_FILE):
                    with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                        last_sent_url = f.read().strip()

                if latest_url != last_sent_url:
                    print(f"🆕 Обнаружено новое расписание: {date_str}. Отправляю в группу...")
                    file_response = session.get(latest_url, timeout=30)
                    if file_response.status_code == 200:
                        sent_msg = bot.send_document(
                            chat_id=CHAT_ID,
                            document=file_response.content,
                            visible_file_name=f"{date_str}.pdf",
                            caption=f"📅 Расписание на {date_str}"
                        )
                        
                        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                            f.write(latest_url)

                        with open(MSG_ID_FILE, 'w', encoding='utf-8') as f:
                            f.write(str(sent_msg.message_id))
                            
                        print(f"✅ Расписание на {date_str} успешно отправлено автоматически!")
        except Exception as e:
            print(f"⚠️ Ошибка в фоновом потоке проверки: {e}")

        # Ждем 30 минут (1800 секунд)
        time.sleep(1800)

# Реакция на команду /r или слово "расписание"
@bot.message_handler(commands=['r'])
@bot.message_handler(func=lambda message: message.text and 'расписание' in message.text.lower())
def handle_schedule_request(message):
    if message.from_user.id not in ALLOWED_USERS:
        return

    latest_url, date_str = find_schedule_by_date()
    
    if not latest_url:
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

    if latest_url == last_sent_url and last_msg_id:
        deleted = True
        try:
            bot.edit_message_caption(chat_id=CHAT_ID, message_id=last_msg_id, caption=f"📅 Расписание на {date_str}")
            deleted = False
        except telebot.apihelper.ApiException as e:
            if "message is not modified" in str(e).lower():
                deleted = False
            else:
                deleted = True

        if not deleted:
            bot.reply_to(message, f"ℹ️ Расписание на {date_str} уже есть в группе. Нового пока нет.")
            return

    try:
        file_response = session.get(latest_url, timeout=30)
        
        if file_response.status_code == 200:
            sent_msg = bot.send_document(
                chat_id=CHAT_ID,
                document=file_response.content,
                visible_file_name=f"{date_str}.pdf",
                caption=f"📅 Расписание на {date_str}"
            )
            
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                f.write(latest_url)

            with open(MSG_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(str(sent_msg.message_id))
                
            bot.reply_to(message, f"✅ Расписание на {date_str} успешно отправлено в группу!")
        else:
            bot.reply_to(message, f"❌ Ошибка скачивания файла (код {file_response.status_code}).")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при отправке: {e}")

if __name__ == '__main__':
    # Запускаем фоновый поток проверки расписания параллельно с ботом
    checker_thread = threading.Thread(target=background_schedule_checker, daemon=True)
    checker_thread.start()

    print("🤖 Бот запущен, работает автономно и проверяет расписание каждые 30 минут!")
    bot.infinity_polling()

