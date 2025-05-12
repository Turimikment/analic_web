from flask import Flask, render_template, request, jsonify, abort, redirect, url_for,session
from flasgger import Swagger, swag_from
import psycopg2
from psycopg2 import sql, errors
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
from psycopg2.extras import DictCursor
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel, Array
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import os
from urllib.parse import urlparse

app = Flask(__name__)

app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/soap-interface')
def soap_interface():
    return render_template('soap.html')
@app.route('/create-user', methods=['GET', 'POST'])
def create_user():
    form_errors = {}
    form_data = session.get('form_data', {})
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        cache_data = 'cache_data' in request.form  # Получаем состояние чекбокса

        # Валидация
        if len(username) < 3 or len(username) > 20:
            form_errors['username'] = 'Имя пользователя должно быть от 3 до 20 символов'
        
        if not validate_email(email):
            form_errors['email'] = 'Некорректный формат email'
        
        if len(password) < 6:
            form_errors['password'] = 'Пароль должен быть не менее 6 символов'

        if form_errors:
            # Сохраняем данные в сессии если чекбокс активен
            if cache_data:
                session['form_data'] = {
                    'username': username,
                    'email': email,
                    'cache_checked': True
                }
            else:
                session.pop('form_data', None)
            
            return render_template('create_user.html', 
                errors=form_errors,
                username=username,
                email=email,
                cache_checked=cache_data)

        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    password_hash = generate_password_hash(password)
                    cursor.execute('''
                        INSERT INTO accounts (username, email, password_hash, creation_method)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    ''', (username, email, password_hash, 'interface'))
                    user_id = cursor.fetchone()[0]
                    conn.commit()
                    session.pop('form_data', None)  # Очищаем кэш после успешной регистрации
                    return redirect(url_for('user_profile', user_id=user_id))

        except errors.UniqueViolation as e:
            if 'username' in str(e):
                form_errors['username'] = 'Имя пользователя уже занято'
            elif 'email' in str(e):
                form_errors['email'] = 'Этот email уже зарегистрирован'
            
            # Сохраняем данные при ошибке БД если чекбокс активен
            if cache_data:
                session['form_data'] = {
                    'username': username,
                    'email': email,
                    'cache_checked': True
                }
            return render_template('create_user.html', 
                errors=form_errors,
                username=username,
                email=email,
                cache_checked=cache_data)
        
        except psycopg2.Error as e:
            form_errors['database'] = f'Ошибка базы данных: {str(e)}'
            if cache_data:
                session['form_data'] = {
                    'username': username,
                    'email': email,
                    'cache_checked': True
                }
            return render_template('create_user.html', 
                errors=form_errors,
                username=username,
                email=email,
                cache_checked=cache_data)

    # GET запрос - используем данные из сессии
    return render_template('create_user.html',
        errors={},
        username=form_data.get('username', ''),
        email=form_data.get('email', ''),
        cache_checked=form_data.get('cache_checked', False))
    
# Схемы данных Swagger
account_model = {
    'type': 'object',
    'properties': {
        'id': {
            'type': 'integer',
            'readOnly': True,
            'description': 'Уникальный идентификатор пользователя',
            'example': 1
        },
        'username': {
            'type': 'string',
            'description': 'Имя пользователя (3-20 символов)',
            'minLength': 3,
            'maxLength': 20,
            'example': 'john_doe'
        },
        'email': {
            'type': 'string',
            'format': 'email',
            'description': 'Валидный email-адрес',
            'example': 'user@example.com'
        },
        'about_me': {
            'type': 'string',
            'description': 'Информация о пользователе',
            'example': 'Разработчик из Москвы',
            'default': ''
        },
        'creation_method' : {
        'type': 'string',
        'description': 'Метод создания пользователя',
        'enum': ['rest', 'soap', 'interface'],
        'example': 'rest'
        }
    }
}

create_account_model = {
    'type': 'object',
    'required': ['username', 'email', 'password'],
    'properties': {
        'username': {
            'type': 'string',
            'description': 'Имя пользователя (3-20 символов)',
            'minLength': 3,
            'maxLength': 20,
            'example': 'jane_doe'
        },
        'email': {
            'type': 'string',
            'format': 'email',
            'description': '''Валидный email-адрес. Требования:
- Должен содержать @
- Локальная часть (до @): буквы, цифры, .! # $ % & ' * + - / = ? ^ _ ` { | } ~
- Доменная часть (после @): минимум одна точка, буквы/цифры и дефисы''',
            'example': 'user@example.com'
        },
        'password': {
            'type': 'string',
            'description': 'Пароль (минимум 6 символов)',
            'minLength': 6,
            'example': 'secret123'
        }
    }
}

update_username_model = {
    'type': 'object',
    'required': ['new_username'],
    'properties': {
        'new_username': {
            'type': 'string',
            'description': 'Новое имя пользователя',
            'minLength': 3,
            'maxLength': 20,
            'example': 'new_username123'
        }
    }
}

about_me_model = {
    'type': 'object',
    'required': ['about_me'],
    'properties': {
        'about_me': {
            'type': 'string',
            'description': 'Информация о пользователе',
            'example': 'Люблю программирование и путешествия',
            'maxLength': 500
        }
    }
}

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "definitions": {
        "Account": account_model,
        "CreateAccount": create_account_model,
        "UpdateUsername": update_username_model,
        "AboutMe": about_me_model
    }
}
# ====== Добавить в раздел моделей Swagger ======
holiday_model = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'readOnly': True},
        'start_time': {
            'type': 'string', 
            'format': 'date-time',
            'example': '2024-03-15T18:00:00Z'
        },
        'location': {
            'type': 'string',
            'example': 'Морковный луг №5'
        },
        'title': {
            'type': 'string',
            'example': 'Фестиваль весенней моркови'
        }
    }
}

Swagger(app, config=swagger_config)

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
                title VARCHAR(100) NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_holidays (
                user_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                holiday_id INTEGER REFERENCES holidays(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, holiday_id)
            )
        ''')
    conn.commit()

def validate_email(email):
    """Проверяет валидность email адреса"""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

@app.route('/profile/<int:user_id>')
def user_profile(user_id):
    """Страница профиля пользователя"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT username, email, about_me 
                    FROM accounts 
                    WHERE id = %s
                ''', (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    abort(404)
                
                return render_template('profile.html', user={
                    'username': user[0],
                    'email': user[1],
                    'about_me': user[2]
                })
                
    except psycopg2.Error as e:
        abort(500, description="Ошибка базы данных")

@app.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        selected_table = request.args.get('table', 'accounts')
        
        with get_db() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Получаем список таблиц
                cursor.execute('''
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                ''')
                tables = [row['table_name'] for row in cursor.fetchall()]
                
                # Получаем данные для выбранной таблицы
                if selected_table == 'accounts':
                    cursor.execute('SELECT * FROM accounts')
                    data = cursor.fetchall()
                elif selected_table == 'holidays':
                    cursor.execute('SELECT * FROM holidays ORDER BY start_time')
                    data = cursor.fetchall()
                elif selected_table == 'user_holidays':
                    cursor.execute('SELECT * FROM user_holidays')
                    data = cursor.fetchall()
                else:
                    data = []

        return render_template(
            'view_db.html',
            tables=tables,
            selected_table=selected_table,
            data=data
        )

    except Exception as e:
        app.logger.error(f"Database access error: {str(e)}")
        return render_template('error.html', error=str(e)), 500

@app.route('/accounts', methods=['GET'])
@swag_from({
    'tags': ['Accounts'],
    'responses': {
        200: {
            'description': 'Список всех учетных записей',
            'schema': {
                'type': 'array',
                'items': account_model
            }
        },
        500: {'description': 'Ошибка базы данных'}
    }
})
def get_accounts():
    """Получить всех зайцев"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id, username, email, about_me,creation_method FROM accounts')
                results = cursor.fetchall()
                accounts = [{
                        'id': row[0],
                        'username': row[1],
                        'email': row[2],
                        'about_me': row[3],
                        'creation_method': row[4]
} for row in results]
                return jsonify(accounts), 200
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts', methods=['POST'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': create_account_model
        }
    ],
    'responses': {
        201: {
            'description': 'Созданная учетная запись',
            'schema': account_model
        },
        400: {'description': 'Некорректные данные'},
        409: {'description': 'Конфликт данных'}
    }
})
def create_account():
    """Создать нового зайца"""
    data = request.get_json()
    validation_errors = {}
    
    username = data.get('username', '')
    email = data.get('email', '')
    password = data.get('password', '')
    
    if len(username) < 3 or len(username) > 20:
        validation_errors['username'] = 'Длина имени должна быть 3-20 символов'
    
    if not validate_email(email):
        validation_errors['email'] = 'Некорректный формат email'
    
    if len(password) < 6:
        validation_errors['password'] = 'Пароль должен быть не менее 6 символов'
    
    if validation_errors:
        return jsonify(errors), 400
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                password_hash = generate_password_hash(password)
                
                cursor.execute('''
                    INSERT INTO accounts (username, email, password_hash, creation_method)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, username, email, about_me, creation_method
                ''', (username, email, password_hash, 'rest'))
                
                new_user = cursor.fetchone()
                conn.commit()
                
                return jsonify({
                    'id': new_user[0],
                    'username': new_user[1],
                    'email': new_user[2],
                    'about_me': new_user[3],
                    'creation_method': new_user[4]
                }), 201

    except errors.UniqueViolation as e:
        error_msg = 'Ошибка уникальности: '
        # Проверка, какое поле вызвало конфликт
        if 'username' in str(e):
            error_msg += 'Имя пользователя уже существует'
        elif 'email' in str(e):
            error_msg += 'Email уже зарегистрирован'
        else:
            error_msg += 'Дубликат данных'
        return jsonify({'error': error_msg}), 409
    
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
    
    except Exception as e:
        return jsonify({'error': 'Неизвестная ошибка'}), 500
        
@app.route('/accounts/<int:user_id>', methods=['PUT'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': update_username_model
        }
    ],
    'responses': {
        200: {
            'description': 'Обновленные данные пользователя',
            'schema': account_model
        },
        400: {'description': 'Некорректные данные'},
        404: {'description': 'Пользователь не найден'},
        409: {'description': 'Имя пользователя уже занято'}
    }
})
def update_username(user_id):
    """Обновить имя изайца"""
    data = request.get_json()
    new_username = data.get('new_username', '').strip()
    
    if not new_username or len(new_username) < 3:
        return jsonify({'error': 'Некорректное имя пользователя'}), 400
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id FROM accounts WHERE id = %s', (user_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                cursor.execute('''
                    UPDATE accounts 
                    SET username = %s
                    WHERE id = %s
                    RETURNING id, username, email, about_me
                ''', (new_username, user_id))
                
                updated_user = cursor.fetchone()
                conn.commit()
                
                return jsonify({
                    'id': updated_user[0],
                    'username': updated_user[1],
                    'email': updated_user[2],
                    'about_me': updated_user[3]
                }), 200
                
    except errors.UniqueViolation as e:
        return jsonify({'error': 'Имя пользователя уже занято'}), 409
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts/about/<int:user_id>', methods=['PUT'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True
        },
        {
            'name': 'about_me',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'about_me': {'type': 'string'}
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Обновленные данные пользователя',
            'schema': account_model
        },
        404: {'description': 'Пользователь не найден'}
    }
})
def update_about_me(user_id):
    """Обновить поле Любимые занятия"""
    data = request.get_json()
    about_me = data.get('about_me', '')
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE accounts 
                    SET about_me = %s
                    WHERE id = %s
                    RETURNING id, username, email, about_me
                ''', (about_me, user_id))
                
                updated_user = cursor.fetchone()
                if not updated_user:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                conn.commit()
                
                return jsonify({
                    'id': updated_user[0],
                    'username': updated_user[1],
                    'email': updated_user[2],
                    'about_me': updated_user[3]
                }), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
@app.route('/accounts/about/<int:user_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True
        }
    ],
    'responses': {
        200: {
            'description': 'Информация "О себе" успешно удалена',
            'schema': account_model
        },
        404: {'description': 'Пользователь не найден'},
        500: {'description': 'Ошибка базы данных'}
    }
})
def delete_about_me(user_id):
    """Удалить информацию из поля любитмые занятия"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE accounts 
                    SET about_me = ''
                    WHERE id = %s
                    RETURNING id, username, email, about_me
                ''', (user_id,))
                
                updated_user = cursor.fetchone()
                if not updated_user:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                conn.commit()
                
                return jsonify({
                    'id': updated_user[0],
                    'username': updated_user[1],
                    'email': updated_user[2],
                    'about_me': updated_user[3]
                }), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts/<int:user_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True
        }
    ],
    'responses': {
        200: {'description': 'Пользователь успешно удален'},
        404: {'description': 'Пользователь не найден'},
        500: {'description': 'Ошибка базы данных'}
    }
})
def delete_account(user_id):
    """Удалить зайца по ID"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM accounts WHERE id = %s', (user_id,))
                if cursor.rowcount == 0:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                conn.commit()
                return jsonify({'message': 'Пользователь успешно удален'}), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
# ... (предыдущий код остается без изменений)
# ====== Эндпоинты для работы с праздниками ======
@app.route('/holidays', methods=['POST'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{
        'name': 'body',
        'in': 'body',
        'required': True,
        'schema': {
            'type': 'object',
            'required': ['start_time', 'location', 'title'],
            'properties': {
                'start_time': {'$ref': '#/definitions/Holiday/properties/start_time'},
                'location': {'$ref': '#/definitions/Holiday/properties/location'},
                'title': {'$ref': '#/definitions/Holiday/properties/title'}
            }
        }
    }],
    'responses': {
        201: {'description': 'Праздник создан', 'schema': holiday_model},
        400: {'description': 'Некорректные данные'}
    }
})
def create_holiday():
    """Создать новый праздник"""
    data = request.get_json()
    
    if not all(key in data for key in ['start_time', 'location', 'title']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO holidays (start_time, location, title)
                    VALUES (%s, %s, %s)
                    RETURNING id, start_time, location, title
                ''', (data['start_time'], data['location'], data['title']))
                
                new_holiday = cursor.fetchone()
                conn.commit()
                
                return jsonify({
                    'id': new_holiday[0],
                    'start_time': new_holiday[1],
                    'location': new_holiday[2],
                    'title': new_holiday[3]
                }), 201
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500

@app.route('/holidays/<int:holiday_id>/attend', methods=['POST'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [
        {
            'name': 'holiday_id',
            'in': 'path',
            'type': 'integer',
            'required': True
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'required': ['user_id'],
                'properties': {
                    'user_id': {
                        'type': 'integer',
                        'example': 1
                    }
                }
            }
        }
    ],
    'responses': {
        200: {'description': 'Пользователь записан'},
        404: {'description': 'Пользователь или праздник не найден'},
        409: {'description': 'Пользователь уже записан'}
    }
})
def add_user_to_holiday(holiday_id):
    """Записать пользователя на праздник"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Проверка существования пользователя и праздника
                cursor.execute('SELECT 1 FROM accounts WHERE id = %s', (user_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'User not found'}), 404
                    
                cursor.execute('SELECT 1 FROM holidays WHERE id = %s', (holiday_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'Holiday not found'}), 404
                
                # Проверка существующей записи
                cursor.execute('''
                    SELECT 1 FROM user_holidays 
                    WHERE user_id = %s AND holiday_id = %s
                ''', (user_id, holiday_id))
                if cursor.fetchone():
                    return jsonify({'error': 'User already registered'}), 409
                
                # Добавление записи
                cursor.execute('''
                    INSERT INTO user_holidays (user_id, holiday_id)
                    VALUES (%s, %s)
                ''', (user_id, holiday_id))
                
                conn.commit()
                return jsonify({'message': 'User added to holiday'}), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500

@app.route('/holidays/<int:holiday_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{
        'name': 'holiday_id',
        'in': 'path',
        'type': 'integer',
        'required': True
    }],
    'responses': {
        200: {'description': 'Праздник удален'},
        404: {'description': 'Праздник не найден'}
    }
})
def delete_holiday(holiday_id):
    """Удалить праздник"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Каскадное удаление через ON DELETE CASCADE
                cursor.execute('DELETE FROM holidays WHERE id = %s', (holiday_id,))
                if cursor.rowcount == 0:
                    return jsonify({'error': 'Holiday not found'}), 404
                
                conn.commit()
                return jsonify({'message': 'Holiday deleted'}), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500

# ====== Обновить Swagger definitions ======
swagger_config['definitions']['Holiday'] = holiday_model
# ====== Добавить в Swagger-определения ======
@app.route('/holidays/<int:holiday_id>/attendees', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [
        {
            'name': 'holiday_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID праздника'
        }
    ],
    'responses': {
        200: {
            'description': 'Список участников праздника',
            'schema': {
                'type': 'array',
                'items': account_model
            }
        },
        404: {'description': 'Праздник не найден'}
    }
})
def get_holiday_attendees(holiday_id):
    """Получить список зайцев, идущих на праздник"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Проверка существования праздника
                cursor.execute('SELECT 1 FROM holidays WHERE id = %s', (holiday_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'Holiday not found'}), 404
                
                # Получение участников
                cursor.execute('''
                    SELECT a.id, a.username, a.email, a.about_me, a.creation_method 
                    FROM accounts a
                    JOIN user_holidays uh ON a.id = uh.user_id
                    WHERE uh.holiday_id = %s
                ''', (holiday_id,))
                
                attendees = [{
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'about_me': row[3],
                    'creation_method': row[4]
                } for row in cursor.fetchall()]
                
                return jsonify(attendees), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500
# ====== Добавить в раздел Swagger-эндпоинтов ======
@app.route('/users/<int:user_id>/holidays', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'ID пользователя'
        }
    ],
    'responses': {
        200: {
            'description': 'Список праздников пользователя',
            'schema': {
                'type': 'array',
                'items': holiday_model
            }
        },
        404: {'description': 'Пользователь не найден'}
    }
})
def get_user_holidays(user_id):
    """Получить список праздников, на которые записан заяц"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Проверка существования пользователя
                cursor.execute('SELECT 1 FROM accounts WHERE id = %s', (user_id,))
                if not cursor.fetchone():
                    return jsonify({'error': 'User not found'}), 404
                
                # Получение праздников пользователя
                cursor.execute('''
                    SELECT h.id, h.start_time, h.location, h.title 
                    FROM holidays h
                    JOIN user_holidays uh ON h.id = uh.holiday_id
                    WHERE uh.user_id = %s
                    ORDER BY h.start_time
                ''', (user_id,))
                
                holidays = [{
                    'id': row[0],
                    'start_time': row[1].isoformat(),
                    'location': row[2],
                    'title': row[3]
                } for row in cursor.fetchall()]
                
                return jsonify(holidays), 200
                
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500
    
class SoapUser(ComplexModel):
    __namespace__ = 'soap.users'
    id = Integer
    username = Unicode
    email = Unicode
    about_me = Unicode
    creation_method = Unicode


class SoapUserRequest(ComplexModel):
    __namespace__ = 'soap.users'
    username = Unicode
    email = Unicode
    password = Unicode
    about_me = Unicode(default='')

class SoapResponse(ComplexModel):
    __namespace__ = 'soap.users'
    status = Unicode
    message = Unicode
    user = SoapUser.customize(min_occurs=0)

class SoapAccountService(ServiceBase):
    @rpc(Integer, _returns=SoapUser)
    def get_user_by_id(ctx, user_id):
        """Получить пользователя по ID"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id, username, email, about_me, creation_method
                        FROM accounts 
                        WHERE id = %s
                    ''', (user_id,))
                    user = cursor.fetchone()
                    if not user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    return SoapUser(
                        id=user[0],
                        username=user[1],
                        email=user[2],
                        about_me=user[3] or '',
                        creation_method = user[4]                        
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(_returns=Array(SoapUser))
    def get_all_users(ctx):
        """Получить всех зайцев"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    # Исправленный SQL-запрос без WHERE
                    cursor.execute('''
                        SELECT id, username, email, about_me, creation_method
                        FROM accounts
                    ''')
                    
                    # Обработка всех записей
                    return [
                        SoapUser(
                            id=row[0],
                            username=row[1],
                            email=row[2],
                            about_me=row[3] or '',
                            creation_method=row[4]
                        )
                        for row in cursor.fetchall()
                    ]
                
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')
    
    @rpc(SoapUserRequest, _returns=SoapResponse)
    def create_user(ctx, user_data):
        """Создать нового зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    password_hash = generate_password_hash(user_data.password)
                    cursor.execute('''
                        INSERT INTO accounts (username, email, password_hash, about_me, creation_method)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, username, email, about_me, creation_method
                    ''', (
                        user_data.username,
                        user_data.email,
                        password_hash,
                        user_data.about_me,
                        'soap'
                    ))
                    new_user = cursor.fetchone()
                    conn.commit()
                    return SoapResponse(
                        # ... остальные поля
                        user=SoapUser(
                        id=updated_user[0],
                        username=updated_user[1],
                        email=updated_user[2],
                        about_me=updated_user[3] or '',
                        creation_method=updated_user[4]
                        )
                    )
        except errors.UniqueViolation as e:
            raise Fault(faultcode='Client', faultstring='Duplicate username or email')
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')



    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_username(ctx, user_id, new_username):
        """Обновить имя зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET username = %s
                        WHERE id = %s
                        RETURNING id, username, email, about_me, creation_method
                    ''', (new_username, user_id))
                
                    updated_user = cursor.fetchone()
                
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                
                    conn.commit()
                
                    return SoapResponse(
                        status='success',
                        message='Username updated',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or '',
                            creation_method=updated_user[4]
                        )
                    )
                
        except errors.UniqueViolation as e:
            raise Fault(faultcode='Client', faultstring='Username already exists')
        
        except psycopg2.Error as e:
            conn.rollback()
            raise Fault(faultcode='Server', faultstring='Database error')


    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_about_me(ctx, user_id, about_text):
        """Обновить информацию в поле Любимые занятия"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET about_me = %s
                        WHERE id = %s
                        RETURNING id, username, email, about_me
                    ''', (about_text, user_id))
                    updated_user = cursor.fetchone()
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='About me updated',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or ''
                        )
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_about_me(ctx, user_id):
        """Удалить информацию из поля Любимые занятия'"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET about_me = ''
                        WHERE id = %s
                        RETURNING id, username, email, about_me
                    ''', (user_id,))
                    updated_user = cursor.fetchone()
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='About me cleared',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or ''
                        )
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_user(ctx, user_id):
        """Удалить зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM accounts WHERE id = %s RETURNING id', (user_id,))
                    if cursor.rowcount == 0:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='User deleted',
                        user=None
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

# Настройка SOAP endpoint
soap_app = Application(
    [SoapAccountService],
    tns='soap.users',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/soap': WsgiApplication(soap_app)
})

# ... (остальной код остается без изменений)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
