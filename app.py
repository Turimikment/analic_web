from flask import Flask, render_template, request, jsonify, abort
from flasgger import Swagger, swag_from
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app = Flask(__name__)

app.config['DATABASE'] = 'accounts.db'
app.config['SECRET_KEY'] = 'supersecretkey'

@app.route('/')
def home():
    return render_template('index.html')


    

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
    "definitions": {  # Используйте "definitions" вместо "components"
        "Account": account_model,
        "CreateAccount": create_account_model,
        "UpdateUsername": update_username_model,
        "AboutMe": about_me_model
    }
}

Swagger(app, config=swagger_config)  # Передаем конфигурацию

def get_db():
    """Возвращает соединение с базой данных"""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with sqlite3.connect('accounts.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
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
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username, email, about_me 
                FROM accounts 
                WHERE id = ?
            ''', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                abort(404)
            
            return render_template('profile.html', user=dict(user))
            
    except sqlite3.Error as e:
        abort(500, description="Ошибка базы данных")
@app.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
        # Получаем данные из таблицы accounts
            cursor.execute('''
                SELECT id, username, email, about_me
                FROM accounts
                ''')
            accounts = cursor.fetchall()
            
            # Получаем список всех таблиц в БД
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in cursor.fetchall()]
            
        return render_template('view_db.html',
                         accounts=accounts,
                         tables=tables)
    
    except Exception as e:
        return render_template('error.html', error=str(e))


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
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email, about_me FROM accounts')
            return jsonify([dict(row) for row in cursor.fetchall()]), 200
    except sqlite3.Error as e:
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
    errors = {}
    
    # Валидация данных
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
            cursor = conn.cursor()
            password_hash = generate_password_hash(password)
            
            cursor.execute('''
                INSERT INTO accounts (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (username, email, password_hash))
            
            conn.commit()
            
            new_user = {
                'id': cursor.lastrowid,
                'username': username,
                'email': email,
                'about_me': ''
            }
            return jsonify(new_user), 201
            
    except sqlite3.IntegrityError as e:
        error_msg = 'Ошибка уникальности: '
        if 'username' in str(e):
            error_msg += 'Имя пользователя уже существует'
        elif 'email' in str(e):
            error_msg += 'Email уже зарегистрирован'
        return jsonify({'error': error_msg}), 409

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
    """Обновить кличку зайца"""
    data = request.get_json()
    new_username = data.get('new_username', '').strip()
    
    if not new_username or len(new_username) < 3:
        return jsonify({'error': 'Некорректное имя пользователя'}), 400
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Проверка существования пользователя
            cursor.execute('SELECT id FROM accounts WHERE id = ?', (user_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Пользователь не найден'}), 404
            
            # Проверка уникальности имени
            cursor.execute('SELECT id FROM accounts WHERE username = ? AND id != ?', 
                         (new_username, user_id))
            if cursor.fetchone():
                return jsonify({'error': 'Имя пользователя уже занято'}), 409
            
            # Обновление данных
            cursor.execute('''
                UPDATE accounts 
                SET username = ?
                WHERE id = ?
            ''', (new_username, user_id))
            
            conn.commit()
            
            # Получение обновленных данных
            cursor.execute('''
                SELECT id, username, email, about_me 
                FROM accounts 
                WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            return jsonify(dict(user)), 200
            
    except sqlite3.Error as e:
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
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE accounts 
                SET about_me = ?
                WHERE id = ?
            ''', (about_me, user_id))
            
            if cursor.rowcount == 0:
                return jsonify({'error': 'Пользователь не найден'}), 404
            
            conn.commit()
            
            cursor.execute('SELECT * FROM accounts WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            return jsonify(dict(user)), 200
            
    except sqlite3.Error as e:
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
            with sqlite3.connect(app.config['DATABASE']) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email, about_me 
                    FROM accounts 
                    WHERE id = ?
                ''', (user_id,))
                
                user = cursor.fetchone()
                if not user:
                    raise Fault(faultcode='Client', 
                              faultstring='User not found')
                
                return SoapUser(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    about_me=user['about_me'] or ''
                )
                
        except sqlite3.Error as e:
            raise Fault(faultcode='Server', 
                      faultstring='Database error')
        except Exception as e:
            raise Fault(faultcode='Server', 
                      faultstring='Internal server error')

# Добавляем SOAP endpoint
soap_app = Application(
    [SoapAccountService],
    tns='soap.users',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/soap': WsgiApplication(soap_app)
})      
 
# Инициализация базы данных
if __name__ == '__main__':
    init_db()
    app.run()
