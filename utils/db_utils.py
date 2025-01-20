# utils/db_utils.py
import pandas as pd
import os

ORDERS_FILE = 'data/orders.csv'
USERS_FILE = 'data/users.csv'

def save_order(user_id, service, date_time,address):
    # Данные, которые нужно сохранить
    data = {'user_id': user_id, 'service': service, 'date_time': date_time, "address": address}
    
    # Создаем DataFrame из данных
    df = pd.DataFrame([data])
    
    # Сохраняем в файл
    df.to_csv(ORDERS_FILE, mode='a', header=False, index=False)

def save_user(user_id, username, full_name, phone_number):
    # Проверяем, существует ли файл, если нет — создаем его с заголовками
    if not os.path.exists(USERS_FILE):
        df = pd.DataFrame(columns=['user_id', 'username', 'full_name', 'phone_number'])
        df.to_csv(USERS_FILE, index=False)

    # Загружаем существующих пользователей
    df = pd.read_csv(USERS_FILE)

    # Проверяем, есть ли пользователь уже в базе
    if user_id in df['user_id'].values:
        return  # Если есть, просто выходим

    # Добавляем нового пользователя
    new_user = pd.DataFrame([{'user_id': user_id, 'username': username, 'full_name': full_name, 'phone_number': phone_number}])
    df = pd.concat([df, new_user], ignore_index=True)

    # Сохраняем обновлённые данные
    df.to_csv(USERS_FILE, index=False)