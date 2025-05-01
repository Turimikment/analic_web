from flask import Flask, render_template
from flask_restx import Api, Resource, fields, reqparse
import psycopg2  # Заменяем sqlite3 на psycopg2
from psycopg2.extras import DictCursor  # Для работы со словарями
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
import os  # Для работы с переменными окружения

# ... (остальной импорт остается без изменений) ...

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['ERROR_404_HELP'] = False

# Конфигурация PostgreSQL
app.config['POSTGRES_HOST'] = os.environ.get('PG_HOST', 'dpg-d09ln50gjchc7398l9bg-a')
app.config['POSTGRES_PORT'] = os.environ.get('PG_PORT', '5432')
app.config['POSTGRES_DB'] = os.environ.get('PG_DATABASE', 'render')
app.config['POSTGRES_USER'] = os.environ.get('PG_USER', 'render')
app.config['POSTGRES_PASSWORD'] = os.environ.get('PG_PASSWORD', 'qtUD994hJSlRfZ79F95fZMDajBKOuVuo')

# Функция подключения к БД
def get_db():
    """Возвращает соединение с PostgreSQL"""
    conn = psycopg2.connect(
        host=app.config['POSTGRES_HOST'],
        port=app.config['POSTGRES_PORT'],
        dbname=app.config['POSTGRES_DB'],
        user=app.config['POSTGRES_USER'],
        password=app.config['POSTGRES_PASSWORD'],
        cursor_factory=DictCursor  # Для работы со словарями
    )
    return conn

# Инициализация БД
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            about_me TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# ... (остальные функции и валидации остаются без изменений) ...

# Пример модифицированного метода
@api.route('/accounts')
class AccountsResource(Resource):
    @api.doc('list_accounts')
    @api.marshal_list_with(account_model)
    def get(self):
        """Получить все учетные записи"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, email, about_me 
                FROM accounts
            ''')
            result = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return result, 200
        except psycopg2.Error as e:  # Изменяем тип исключения
            api.abort(500, 'Ошибка базы данных')

# Модифицируем метод создания аккаунта
@api.route('/accounts')
class AccountsResource(Resource):
    # ... (остальные методы) ...

    @api.doc('create_account')
    @api.expect(create_account_model)
    @api.marshal_with(account_model, code=201)
    def post(self):
        # ... (валидация остается без изменений) ...
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            password_hash = generate_password_hash(args['password'])
            
            cursor.execute('''
                INSERT INTO accounts (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email  # Используем RETURNING
            ''', (args['username'], args['email'], password_hash))
            
            new_account = cursor.fetchone()
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return dict(new_account), 201
                
        except psycopg2.IntegrityError as e:  # Ловим ошибки PostgreSQL
            # Обработка ошибок уникальности
            error_msg = 'Ошибка уникальности: '
            if 'username' in str(e):
                error_msg += 'Имя пользователя уже существует'
            elif 'email' in str(e):
                error_msg += 'Email уже зарегистрирован'
            api.abort(409, error_msg)

# Аналогично модифицируем остальные методы, заменяя:
# 1. sqlite3.connect() → get_db()
# 2. Запросы с ? → %s
# 3. cursor.lastrowid → RETURNING id
# 4. sqlite3.Error → psycopg2.Error

if __name__ == '__main__':
    init_db()
    app.run()
