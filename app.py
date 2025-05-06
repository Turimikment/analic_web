from flask import Flask, render_template, request, jsonify, abort
from flasgger import Swagger, swag_from
import psycopg2
from psycopg2 import sql, errors
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import os
from urllib.parse import urlparse

app = Flask(__name__)

app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/soap-interface')
def soap_interface():
    return render_template('soap.html')

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
                    about_me TEXT DEFAULT ''
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
        with get_db() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Получаем данные пользователей
                cursor.execute('''
                    SELECT id, username, email, about_me
                    FROM accounts
                ''')
                accounts = cursor.fetchall()

                # Получаем список таблиц
                cursor.execute('''
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                ''')
                tables = [row['table_name'] for row in cursor.fetchall()]

        return render_template('view_db.html',
                            accounts=accounts,
                            tables=tables)

    except Exception as e:
        app.logger.error(f"Ошибка при доступе к БД: {str(e)}")
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
    """Получить всех пользователей"""
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT id, username, email, about_me FROM accounts')
                results = cursor.fetchall()
                accounts = [{
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'about_me': row[3]
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
    """Создать нового пользователя"""
    data = request.get_json()
    errors = {}
    
    username = data.get('username', '')
    email = data.get('email', '')
    password = data.get('password', '')
    
    if len(username) < 3 or len(username) > 20:
        errors['username'] = 'Длина имени должна быть 3-20 символов'
    
    if not validate_email(email):
        errors['email'] = 'Некорректный формат email'
    
    if len(password) < 6:
        errors['password'] = 'Пароль должен быть не менее 6 символов'
    
    if errors:
        return jsonify(errors), 400
    
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                password_hash = generate_password_hash(password)
                
                cursor.execute('''
                    INSERT INTO accounts (username, email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING id, username, email, about_me
                ''', (username, email, password_hash))
                
                new_user = cursor.fetchone()
                conn.commit()
                
                return jsonify({
                    'id': new_user[0],
                    'username': new_user[1],
                    'email': new_user[2],
                    'about_me': new_user[3]
                }), 201
                
    except errors.UniqueViolation as e:
        error_msg = 'Ошибка уникальности: '
        if 'username' in str(e):
            error_msg += 'Имя пользователя уже существует'
        elif 'email' in str(e):
            error_msg += 'Email уже зарегистрирован'
        return jsonify({'error': error_msg}), 409
    except psycopg2.Error as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

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
    """Обновить имя пользователя"""
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

@app.route('/accounts/<int:user_id>/about', methods=['PUT'])
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
    """Обновить информацию 'О себе'"""
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

class SoapUser(ComplexModel):
    __namespace__ = 'soap.users'
    id = Integer
    username = Unicode
    email = Unicode
    about_me = Unicode

class SoapAccountService(ServiceBase):
    @rpc(Integer, _returns=SoapUser)
    def get_user_by_id(ctx, user_id):
        """Получить пользователя по ID через SOAP"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id, username, email, about_me 
                        FROM accounts 
                        WHERE id = %s
                    ''', (user_id,))
                    
                    user = cursor.fetchone()
                    if not user:
                        raise Fault(faultcode='Client', 
                                  faultstring='User not found')
                    
                    return SoapUser(
                        id=user[0],
                        username=user[1],
                        email=user[2],
                        about_me=user[3] or ''
                    )
                    
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', 
                      faultstring='Database error')
        except Exception as e:
            raise Fault(faultcode='Server', 
                      faultstring='Internal server error')

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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
