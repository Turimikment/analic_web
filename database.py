import psycopg2
from urllib.parse import urlparse
import os
def get_db():
    """Возвращает соединение с базой данных"""
    conn = psycopg2.connect(app.config['DATABASE_URL'])
    return conn

def init_db():
    """Инициализация базы данных"""
    parsed_url = urlparse(app.config['DATABASE_URL'])
    db_name = parsed_url.path[1:]
    db_user = parsed_url.username
    db_pass = parsed_url.password
    db_host = parsed_url.hostname
    db_port = parsed_url.port

    # Подключаемся к postgres для создания БД
    admin_conn = psycopg2.connect(
        dbname='postgres',
        user=db_user,
        password=db_pass,
        host=db_host,
        port=db_port
    )
    admin_conn.autocommit = True
    admin_cursor = admin_conn.cursor()
    
    # Создаем БД если не существует
    admin_cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    if not admin_cursor.fetchone():
        admin_cursor.execute(f"CREATE DATABASE {db_name}")
    
    admin_cursor.close()
    admin_conn.close()

    # Создаем таблицы
with get_db() as conn:
    with conn.cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                username VARCHAR(20) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                about_me TEXT DEFAULT '',
                creation_method VARCHAR(10) NOT NULL DEFAULT 'interface'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holidays (
                id SERIAL PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                location VARCHAR(255) NOT NULL,
                title VARCHAR(100) NOT NULL UNIQUE  
            )
        ''')


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_holidays (
                id SERIAL PRIMARY KEY,  
                user_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                holiday_id INTEGER REFERENCES holidays(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
                UNIQUE (user_id, holiday_id)  
            )
        ''')
    conn.commit()