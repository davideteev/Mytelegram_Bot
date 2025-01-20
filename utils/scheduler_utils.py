from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

scheduler = AsyncIOScheduler()

def schedule_reminder(user_id: int, text: str, reminder_time: datetime):
    """Функция для планирования напоминания пользователю."""
    scheduler.add_job(
        reminder_task, 
        "date", 
        run_date=reminder_time, 
        args=[user_id, text]
    )

async def reminder_task(user_id: int, text: str):
    """Функция, отправляющая напоминание пользователю."""
    await Bot.send_message(user_id, f"🔔 {text}")