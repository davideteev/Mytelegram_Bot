import sys
import os
import asyncio  # Импортируем asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Импортируем планировщик
from aiogram import Bot, Dispatcher,executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import pandas as pd
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton,BotCommand
from langchain_ollama import OllamaLLM
from aiogram.dispatcher.middlewares import BaseMiddleware
from datetime import datetime, timedelta

llm = OllamaLLM(model="mistral")

# Указать путь к текущей директории проекта
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils.scheduler_utils import schedule_reminder
from utils.db_utils import save_order, save_user, USERS_FILE


# Инициализация бота
bot = Bot(token="7682836473:AAHYlB2aoS814_NFukG78fhboCf-IqDmDT0")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
print("bot запущен")

from aiogram.types import BotCommand

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="order", description="Записаться на замер"),
        BotCommand(command="consult", description="Консультация по дверям и сварке"),
        BotCommand(command="stop_consult", description="Остановить консультацию"),
    ]
    await bot.set_my_commands(commands)

# Запускаем установку команд при старте
async def on_startup(dispatcher):
    await set_bot_commands(dispatcher.bot)
    

# Функция для отправки напоминаний
async def send_reminders():
    users_df = pd.read_csv(USERS_FILE) if os.path.exists(USERS_FILE) else pd.DataFrame(columns=["user_id", "date_time"])

    if users_df.empty:
        return  # Если записей нет, выходим

    now = datetime.now()
    reminder_time = now + timedelta(hours=1)  # Время через 1 час

    for _, row in users_df.iterrows():
        try:
            appointment_time = pd.to_datetime(row["date_time"])  # Переводим дату в datetime
            if appointment_time.strftime("%Y-%m-%d %H:%M") == reminder_time.strftime("%Y-%m-%d %H:%M"):
                await bot.send_message(row["user_id"], "🔔 Напоминание! Ваш замер через 1 час.")
        except Exception as e:
            print(f"Ошибка в отправке напоминания: {e}")
            
            
# Запуск планировщика, который будет проверять напоминания каждую минуту
scheduler = AsyncIOScheduler()
scheduler.add_job(send_reminders, "interval", minutes=1)

# FSM: Состояния для записи
class OrderState(StatesGroup):
    phone_number=State()
    service = State()
    date_time = State()
    address = State()

class UnknownCommandMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        # Если сообщение не текстовое — пропускаем
        if not message.text:
            return
        
        # Проверяем, что это команда, и она отсутствует в разрешённом списке
        if message.text.startswith("/") and message.text not in ["/start", "/order", "/consult", "/stop_consult", "/help"]:
            await message.answer("❌ Неизвестная команда. Введите /help для списка доступных команд.")
            return  # Завершаем обработку неизвестной команды

dp.middleware.setup(UnknownCommandMiddleware())

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    # Проверяем, есть ли пользователь уже в базе
    users_df = pd.read_csv(USERS_FILE) if os.path.exists(USERS_FILE) else pd.DataFrame(columns=["user_id"])
    if message.from_user.id in users_df["user_id"].values:
        await message.answer("Добро пожаловать! Чтобы записаться на замеры, используйте команду /order.")
        return

    # Просим пользователя отправить номер телефона
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton("/📱 Отправить номер", request_contact=True))

    await message.answer("Пожалуйста, отправьте свой номер телефона, нажав на кнопку ниже:", reply_markup=keyboard)
    await OrderState.phone_number.set()
    
@dp.message_handler(content_types=types.ContentType.CONTACT, state=OrderState.phone_number)
async def get_phone_number(message: types.Message, state: FSMContext):
    phone_number = message.contact.phone_number

    # Регистрируем пользователя
    save_user(
        user_id=message.from_user.id, 
        username=message.from_user.username, 
        full_name=message.from_user.full_name,
        phone_number=phone_number
    )

    await message.answer("Спасибо! Вы зарегистрированы. Теперь вы можете записаться на замеры с помощью команды /order.", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

@dp.message_handler(commands=["help"])
async def help_command(message: types.Message):
    help_text = (
        "🔹 Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/order - Записаться на замер\n"
        "/consult - Включить режим консультации\n"
        "/stop_consult - Остановить консультацию\n"
        "/help - Показать список команд"
    )
    await message.answer(help_text)
    
# Команда записи на замеры
@dp.message_handler(commands=["order"])
async def start_order(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Замеры дверей", "Замеры окон", "Сварочные работы", "Замеры под автоматику"]
    keyboard.add(*buttons)
    await message.answer("Выберите услугу:", reply_markup=keyboard)
    await OrderState.service.set()
    
#Работа с нейросетью
user_contexts={}
ai_chat_active={}
@dp.message_handler(commands=["consult"])
async def start_consultation(message: types.Message):
    ai_chat_active[message.from_user.id]=True
    user_contexts[message.from_user.id]=[]
    await message.answer("Вы вошли в режим консультации. Напишите свой вопрос.")
    
@dp.message_handler(commands=["stop_consult"])
async def start_consultation(message: types.Message):
    user_id = message.from_user.id
    ai_chat_active[message.from_user.id]=False
    user_contexts.pop(user_id,None)
    await message.answer("Режим консультации выключен. Вы можете записаться на замер используя команду /order.")
    
    

@dp.message_handler(lambda message: message.from_user.id in ai_chat_active and ai_chat_active[message.from_user.id])
async def ai_consultant(message: types.Message):
    user_id = message.from_user.id
    
    # Если пользователь впервые пишет в режиме ИИ-консультации — создаём ему историю
    if user_id not in user_contexts:
        user_contexts[user_id] = []

    # Добавляем сообщение пользователя в историю
    user_contexts[user_id].append({"role": "user", "content": message.text})

    # Формируем контекстный промпт
    system_prompt = (
        "Ты — консультант по дверям, окнам, сварочным работам и автоматике. "
        "Отвечай строго по теме, не уходи в философию, политику или другие области. "
        "Если вопрос не по теме — скажи, что ты можешь помочь только с дверями, окнами, сваркой и автоматикой."
    )
    
    # Собираем весь контекст диалога
    full_context = system_prompt + "\n" + "\n".join([m["content"] for m in user_contexts[user_id]])

    # Отправляем в нейросеть и получаем ответ
    response = llm.invoke(full_context)

    # Добавляем ответ бота в историю
    user_contexts[user_id].append({"role": "assistant", "content": response})

    # Отправляем ответ пользователю
    await message.answer(response)

# Сохранение услуги
@dp.message_handler(state=OrderState.service)
async def get_service(message: types.Message, state: FSMContext):
    await state.update_data(service=message.text)
    
    await message.answer("Введите дату и время в формате YYYY-MM-DD HH:MM:")
    await OrderState.date_time.set()


# Сохранение даты/времени и переход к адресу
@dp.message_handler(state=OrderState.date_time)
async def get_date_time(message: types.Message, state: FSMContext):
    try:
        print("Получено сообщение с датой:", message.text)

        # Проверка даты/времени
        date_time = pd.to_datetime(message.text, format='%Y-%m-%d %H:%M')
        await state.update_data(date_time=date_time)

        await message.answer("Введите адрес, куда должен приехать мастер:")
        await OrderState.address.set()  # Переход к вводу адреса
    except ValueError:
        await message.answer("Некорректный формат даты/времени. Попробуйте ещё раз.")

# Сохранение адреса и завершение
@dp.message_handler(state=OrderState.address)
async def get_address(message: types.Message, state: FSMContext):
    data = await state.get_data()
    address = message.text
    await state.update_data(address=address)

    # Сохраняем заказ в БД
    save_order(message.from_user.id, data["service"], data["date_time"], address)  # Обновили функцию

    # Формируем сообщение
    response_text = f"Вы записаны на '{data['service']}' в {data['date_time']} по адресу {address}. Спасибо!"

    # Добавляем номер мастера
    if data["service"] in ["Замеры дверей", "Замеры окон"]:
        response_text += "\nНомер Мастера: 8(909)397-19-79"
    elif data["service"] == "Замеры под автоматику":
        response_text += "\nНомер Мастера: +7927283-20-47"
    else:
        response_text += "\nНомер Мастера: 8995552-01-13"

    await message.answer(response_text)
    try:
        appointment_time = pd.to_datetime(data["date_time"], format = '%Y-%m-%d %H:%M')
        reminder_time = appointment_time-timedelta(hours=1)
        schedule_reminder(message.from_user.id,f"🔔 Напоминание! В {data['date_time']} у вас '{data['service']}' по адресу {address}.", reminder_time)
    except Exception as e:
        print(f"Ошибка при планировании напоминания: {e}")
    await state.finish()
    
    
    
async def main():
    await on_startup(dp)
    scheduler.start()  # Запуск APScheduler
    await dp.start_polling()

if __name__ == "main":
    asyncio.run(main())  # Запускаем event loop
executor.start_polling(dp,on_startup=on_startup)