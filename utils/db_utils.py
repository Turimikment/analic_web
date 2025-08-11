import psycopg2
from psycopg2 import sql, errors
from werkzeug.security import generate_password_hash
import os
from urllib.parse import urlparse
from datetime import datetime
from psycopg2.extras import DictCursor
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def get_db_connection():
    """Возвращает соединение с базой данных"""
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn


def init_db():
    """Инициализирует базу данных"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Создание таблицы accounts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(20) UNIQUE NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    about_me TEXT,
                    creation_method VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
                task1 BOOLEAN NOT NULL DEFAULT FALSE,
                task2 BOOLEAN NOT NULL DEFAULT FALSE,
                task3 BOOLEAN NOT NULL DEFAULT FALSE,
                is_full_account BOOLEAN NOT NULL DEFAULT FALSE
                )
            """)
            
            # Создание таблицы holidays
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS holidays (
                    id SERIAL PRIMARY KEY,
                    start_time TIMESTAMP NOT NULL,
                    location VARCHAR(255) NOT NULL,
                    title VARCHAR(100) NOT NULL
                )
            """)
            
            # Создание таблицы user_holidays
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_holidays (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                    holiday_id INTEGER REFERENCES holidays(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def create_account(username, email, password, creation_method, about_me=None):
    """Создает новую учетную запись с хешированным паролем"""
    try:
        # Хешируем пароль
        password_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Проверяем уникальность имени пользователя и email
            cursor.execute(
                "SELECT id FROM accounts WHERE username = %s OR email = %s",
                (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                raise ValueError("Пользователь с таким именем или email уже существует")
            
            # Создаем нового пользователя
            cursor.execute(
                "INSERT INTO accounts (username, email, password_hash, creation_method, about_me) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id, username, email, creation_method",
                (username, email, password_hash, creation_method, about_me)
            )
 
            user = cursor.fetchone()
            cursor.execute(
                "INSERT INTO user_progress (user_id) VALUES (%s)",
                (user[0],)  # user[0] - ID нового пользователя
            )
            conn.commit()

            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'creation_method': user[3]
            }
            
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_account_by_id(user_id):
    """Возвращает аккаунт по ID"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, about_me, creation_method "
                "FROM accounts WHERE id = %s",
                (user_id,)
            )
            user = cursor.fetchone()
            if user:
                return {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'about_me': user[3],
                    'creation_method': user[4]
                }
            return None
    except Exception as e:
        raise e
    finally:
        conn.close()

def get_all_accounts():
    """Получить всех пользователей"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, username, email, about_me, creation_method 
                FROM accounts
            ''')
            return [
                {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'about_me': row[3],
                    'creation_method': row[4]
                }
                for row in cursor.fetchall()
            ]
    finally:
        conn.close()

def update_username(user_id, new_username):
    """Обновить имя пользователя"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE accounts 
                SET username = %s
                WHERE id = %s
                RETURNING id, username, email, about_me, creation_method
            ''', (new_username, user_id))
            updated_user = cursor.fetchone()
            if not updated_user:
                return None
            conn.commit()
            return {
                'id': updated_user[0],
                'username': updated_user[1],
                'email': updated_user[2],
                'about_me': updated_user[3],
                'creation_method': updated_user[4]
            }
    except errors.UniqueViolation:
        conn.rollback()
        raise ValueError('Имя пользователя уже занято')
    finally:
        conn.close()

def update_about_me(user_id, about_me):
    """Обновить информацию 'О себе'"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE accounts 
                SET about_me = %s
                WHERE id = %s
                RETURNING id, username, email, about_me, creation_method
            ''', (about_me, user_id))
            updated_user = cursor.fetchone()
            if not updated_user:
                return None
            conn.commit()
            return {
                'id': updated_user[0],
                'username': updated_user[1],
                'email': updated_user[2],
                'about_me': updated_user[3],
                'creation_method': updated_user[4]
            }
    finally:
        conn.close()

def delete_about_me(user_id):
    """Удалить информацию 'О себе'"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                UPDATE accounts 
                SET about_me = ''
                WHERE id = %s
                RETURNING id, username, email, about_me, creation_method
            ''', (user_id,))
            updated_user = cursor.fetchone()
            if not updated_user:
                return None
            conn.commit()
            return {
                'id': updated_user[0],
                'username': updated_user[1],
                'email': updated_user[2],
                'about_me': updated_user[3],
                'creation_method': updated_user[4]
            }
    finally:
        conn.close()

def delete_account(user_id):
    """Удалить пользователя"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM accounts WHERE id = %s', (user_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count > 0
    finally:
        conn.close()

# Функции для работы с праздниками
def create_holiday(start_time, location, title):
    """Создать новый праздник"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO holidays (start_time, location, title)
                VALUES (%s, %s, %s)
                RETURNING id, start_time, location, title
            ''', (start_time, location, title))
            new_holiday = cursor.fetchone()
            conn.commit()
            return {
                'id': new_holiday[0],
                'start_time': new_holiday[1],
                'location': new_holiday[2],
                'title': new_holiday[3]
            }
    except errors.UniqueViolation:
        conn.rollback()
        raise ValueError('Праздник с таким названием уже существует')
    finally:
        conn.close()

def search_holidays(query):
    """Поиск праздников по названию или локации"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, start_time, location, title 
                FROM holidays 
                WHERE title ILIKE %s OR location ILIKE %s
                ORDER BY start_time
            ''', (f'%{query}%', f'%{query}%'))
            return [{
                'id': row[0],
                'title': row[3],
                'location': row[2],
                'start_time': row[1]
            } for row in cursor.fetchall()]
    finally:
        conn.close()

def get_holiday_attendees(holiday_id):
    """Получить участников праздника"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT a.id, a.username, a.email, a.about_me, a.creation_method 
                FROM accounts a
                JOIN user_holidays uh ON a.id = uh.user_id
                WHERE uh.holiday_id = %s
            ''', (holiday_id,))
            return [{
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'about_me': row[3],
                'creation_method': row[4]
            } for row in cursor.fetchall()]
    finally:
        conn.close()

def get_user_holidays(user_id):
    """Получить праздники пользователя"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT h.id, h.start_time, h.location, h.title 
                FROM holidays h
                JOIN user_holidays uh ON h.id = uh.holiday_id
                WHERE uh.user_id = %s
                ORDER BY h.start_time
            ''', (user_id,))
            return [{
                'id': row[0],
                'start_time': row[1].isoformat() + 'Z',
                'location': row[2],
                'title': row[3]
            } for row in cursor.fetchall()]
    finally:
        conn.close()

def add_user_to_holiday(user_id, holiday_id):
    """Записать пользователя на праздник"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO user_holidays (user_id, holiday_id)
                VALUES (%s, %s)
                RETURNING id, created_at
            ''', (user_id, holiday_id))
            new_entry = cursor.fetchone()
            conn.commit()
            return {
                'id': new_entry[0],
                'created_at': new_entry[1].isoformat()
            }
    except errors.UniqueViolation:
        conn.rollback()
        raise ValueError('Пользователь уже записан на этот праздник')
    finally:
        conn.close()

def delete_holiday(holiday_id):
    """Удалить праздник"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM holidays WHERE id = %s', (holiday_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count > 0
    finally:
        conn.close()
        
def get_table_data(table_name):
    """Получение данных таблицы (упрощенная версия)"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            if table_name == 'accounts':
                cursor.execute("SELECT * FROM accounts")
            elif table_name == 'holidays':
                cursor.execute("SELECT * FROM holidays")
            elif table_name == 'user_holidays':
                cursor.execute("""
                    SELECT 
                        uh.id, uh.user_id, a.username AS user_name, 
                        uh.holiday_id, h.title AS holiday_title, uh.created_at
                    FROM user_holidays uh
                    LEFT JOIN accounts a ON uh.user_id = a.id
                    LEFT JOIN holidays h ON uh.holiday_id = h.id
                """)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
        return data, columns
    finally:
        conn.close()
def get_table_data(table_name):
    """Получение данных таблицы и SQL-запроса"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            if table_name == 'accounts':
                sql_query = "SELECT * FROM accounts;"
                cursor.execute(sql_query)
                
            elif table_name == 'holidays':
                sql_query = "SELECT * FROM holidays ORDER BY start_time;"
                cursor.execute(sql_query)
                
            elif table_name == 'user_holidays':
                sql_query = """
                    SELECT 
                        uh.id,
                        uh.user_id,
                        uh.holiday_id,
                        a.username AS user_name,
                        h.title AS holiday_title,
                        uh.created_at
                    FROM user_holidays uh
                    LEFT JOIN accounts a ON uh.user_id = a.id
                    LEFT JOIN holidays h ON uh.holiday_id = h.id
                    ORDER BY uh.created_at DESC;
                """
                cursor.execute(sql_query)
                
            else:
                data = []
                columns = []
                sql_query = ""
                return [], [], ""
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return data, columns, sql_query
            
    finally:
        conn.close()

def format_value(value):
    """Форматирование значений для CSV"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value) if value is not None else ''

def check_user_progress(user_id):
    """Проверяет прогресс выполнения заданий"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT task1, task2, task3, is_full_account "
                "FROM user_progress WHERE user_id = %s",
                (user_id,)
            )
            return cursor.fetchone()
    finally:
        conn.close()