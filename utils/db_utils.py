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
    """Инициализация базы данных с проверкой существования таблиц"""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL not set in environment")
        return
    
    parsed_url = urlparse(db_url)
    db_name = parsed_url.path[1:]
    db_user = parsed_url.username
    db_pass = parsed_url.password
    db_host = parsed_url.hostname
    db_port = parsed_url.port

    # Подключаемся к postgres для создания БД
    try:
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
            logger.info(f"Creating database: {db_name}")
            admin_cursor.execute(f"CREATE DATABASE {db_name}")
        else:
            logger.info(f"Database {db_name} already exists")
        
        admin_cursor.close()
        admin_conn.close()
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        return

    # Создаем таблицы в целевой БД
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cursor:
                # Проверяем существование таблицы accounts
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'accounts')")
                if not cursor.fetchone()[0]:
                    logger.info("Creating table: accounts")
                    cursor.execute('''
                        CREATE TABLE accounts (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(20) NOT NULL UNIQUE,
                            email VARCHAR(255) NOT NULL UNIQUE,
                            password_hash VARCHAR(255) NOT NULL,
                            about_me TEXT DEFAULT '',
                            creation_method VARCHAR(10) NOT NULL DEFAULT 'interface'
                        )
                    ''')
                
                # Проверяем существование таблицы holidays
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'holidays')")
                if not cursor.fetchone()[0]:
                    logger.info("Creating table: holidays")
                    cursor.execute('''
                        CREATE TABLE holidays (
                            id SERIAL PRIMARY KEY,
                            start_time TIMESTAMP NOT NULL,
                            location VARCHAR(255) NOT NULL,
                            title VARCHAR(100) NOT NULL UNIQUE  
                        )
                    ''')
                
                # Проверяем существование таблицы user_holidays
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_holidays')")
                if not cursor.fetchone()[0]:
                    logger.info("Creating table: user_holidays")
                    cursor.execute('''
                        CREATE TABLE user_holidays (
                            id SERIAL PRIMARY KEY,  
                            user_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                            holiday_id INTEGER REFERENCES holidays(id) ON DELETE CASCADE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
                            UNIQUE (user_id, holiday_id)  
                        )
                    ''')
                
                # Проверяем существование индекса для поиска
                cursor.execute("SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = 'idx_holidays_search')")
                if not cursor.fetchone()[0]:
                    logger.info("Creating index: idx_holidays_search")
                    cursor.execute('''
                        CREATE INDEX idx_holidays_search 
                        ON holidays USING gin (to_tsvector('russian', title || ' ' || location))
                    ''')
                
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
    finally:
        if conn:
            conn.close()

# Функции для работы с аккаунтами
def create_account(username, email, password, creation_method='rest', about_me=''):
    """Создать нового пользователя"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO accounts (username, email, password_hash, creation_method, about_me)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, username, email, about_me, creation_method
            ''', (username, email, password_hash, creation_method, about_me))
            new_user = cursor.fetchone()
            conn.commit()
            return {
                'id': new_user[0],
                'username': new_user[1],
                'email': new_user[2],
                'about_me': new_user[3],
                'creation_method': new_user[4]
            }
    except errors.UniqueViolation as e:
        conn.rollback()
        if 'username' in str(e):
            raise ValueError('Имя пользователя уже занято')
        elif 'email' in str(e):
            raise ValueError('Email уже зарегистрирован')
        else:
            raise ValueError('Ошибка уникальности')
    finally:
        conn.close()

def get_account_by_id(user_id):
    """Получить пользователя по ID"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT id, username, email, about_me, creation_method
                FROM accounts 
                WHERE id = %s
            ''', (user_id,))
            user = cursor.fetchone()
            if not user:
                return None
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'about_me': user[3],
                'creation_method': user[4]
            }
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