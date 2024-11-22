import telebot
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import threading
from config import *

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Множество для хранения подписанных пользователей
subscribed_users = set()

class ExchangeRateMonitor:
    def __init__(self):
        self.last_rate = None
        self.is_running = True

    def get_current_rate(self):
        """Получает текущий курс обмена с сайта"""
        try:
            response = requests.get(URL, headers=HEADERS, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # Находим таблицу с курсами
            rate_element = soup.find('div', class_='bi rate-value')
            
            if rate_element:
                # Извлекаем числовое значение курса
                rate_text = rate_element.text.strip().replace(',', '.')
                return float(rate_text)
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении данных: {e}")
            return None
        except Exception as e:
            print(f"Неожиданная ошибка: {e}")
            return None

    def should_notify(self, current_rate):
        """Проверяет, нужно ли отправлять уведомление"""
        if self.last_rate is None:
            return True
        return abs(current_rate - self.last_rate) >= RATE_THRESHOLD

    def send_rate_update(self, rate):
        """Отправляет обновление курса всем подписанным пользователям"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"🔄 Обновление курса!\n\n"
            f"📊 Текущий курс: {rate:.2f}\n"
            f"⏰ Время: {timestamp}"
        )
        
        # Копируем множество, чтобы избежать ошибок при изменении во время итерации
        for user_id in subscribed_users.copy():
            try:
                bot.send_message(user_id, message)
            except telebot.apihelper.ApiException as e:
                if "Forbidden" in str(e):
                    # Пользователь заблокировал бота, удаляем из подписчиков
                    subscribed_users.discard(user_id)
                print(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

    def run(self):
        """Основной цикл мониторинга курса"""
        print("Бот запущен и мониторит курс обмена...")
        
        while self.is_running:
            try:
                current_rate = self.get_current_rate()
                
                if current_rate is not None:
                    if self.should_notify(current_rate):
                        self.send_rate_update(current_rate)
                        self.last_rate = current_rate
                
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                print(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(60)  # Ждём минуту перед повторной попыткой

# Обработчики команд
@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    welcome_text = (
        "👋 Привет! Я бот для мониторинга курса обмена.\n\n"
        "Доступные команды:\n"
        "/subscribe - Подписаться на уведомления\n"
        "/unsubscribe - Отписаться от уведомлений\n"
        "/current - Получить текущий курс\n"
        "/help - Показать это сообщение\n\n"
        "Я буду отправлять уведомления при изменении курса на "
        f"{RATE_THRESHOLD} или более."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help(message):
    """Обработчик команды /help"""
    help_text = (
        "📌 Доступные команды:\n\n"
        "/subscribe - Подписаться на уведомления\n"
        "/unsubscribe - Отписаться от уведомлений\n"
        "/current - Показать текущий курс\n"
        "/help - Показать это сообщение\n\n"
        f"❗️ Бот отправляет уведомления при изменении курса на {RATE_THRESHOLD} или более."
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    """Обработчик команды /subscribe"""
    user_id = message.from_user.id
    if user_id not in subscribed_users:
        subscribed_users.add(user_id)
        bot.reply_to(
            message, 
            "✅ Вы успешно подписались на уведомления об изменении курса!"
        )
    else:
        bot.reply_to(message, "ℹ️ Вы уже подписаны на уведомления.")

@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(message):
    """Обработчик команды /unsubscribe"""
    user_id = message.from_user.id
    if user_id in subscribed_users:
        subscribed_users.remove(user_id)
        bot.reply_to(message, "✅ Вы успешно отписались от уведомлений.")
    else:
        bot.reply_to(message, "ℹ️ Вы не были подписаны на уведомления.")

@bot.message_handler(commands=['current'])
def current_rate(message):
    """Обработчик команды /current"""
    monitor = ExchangeRateMonitor()
    rate = monitor.get_current_rate()
    if rate:
        bot.reply_to(message, f"📊 Текущий курс обмена: {rate:.2f}")
    else:
        bot.reply_to(
            message, 
            "❌ Не удалось получить текущий курс. Попробуйте позже."
        )

def run_bot():
    """Запуск бота"""
    monitor = ExchangeRateMonitor()
    
    # Запуск мониторинга в отдельном потоке
    monitor_thread = threading.Thread(target=monitor.run)
    monitor_thread.daemon = True  # Поток завершится вместе с основной программой
    monitor_thread.start()
    
    try:
        # Запуск бота
        print("Бот запущен. Нажмите Ctrl+C для остановки.")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\nОстановка бота...")
        monitor.is_running = False
        monitor_thread.join()
        print("Бот остановлен.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        monitor.is_running = False
        monitor_thread.join()

if __name__ == "__main__":
    run_bot()