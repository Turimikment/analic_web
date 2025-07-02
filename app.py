from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, session
from flasgger import Swagger, swag_from
import re
import logging
from time import sleep
from psycopg2.extras import DictCursor
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import os
from datetime import datetime
from redis_utils import CarrotStats
import db_utils
from .routes import (
    main_routes
)
app = Flask(__name__)
app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)
carrot_stats = CarrotStats()

app.register_blueprint(main_routes.bp)

@app.route('/create-user', methods=['GET', 'POST'])
def create_user():
    # Упрощенная версия без использования сессии
    form_errors = {}
    username = ''
    email = ''
    cache_checked = False
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        cache_checked = 'cache_data' in request.form

        # Валидация
        if len(username) < 3 or len(username) > 20:
            form_errors['username'] = 'Имя пользователя должно быть от 3 до 20 символов'
        
        if not validate_email(email):
            form_errors['email'] = 'Некорректный формат email'
        
        if len(password) < 6:
            form_errors['password'] = 'Пароль должен быть не менее 6 символов'

        if not form_errors:
            try:
                new_user = db_utils.create_account(
                    username=username,
                    email=email,
                    password=password,
                    creation_method='interface'
                )
                return redirect(url_for('pipeline'))
                
            except ValueError as e:
                form_errors['database'] = str(e)
            except Exception as e:
                form_errors['database'] = f'Ошибка базы данных: {str(e)}'
    
    # Для GET-запросов и POST с ошибками
    return render_template('create_user.html',
        errors=form_errors,
        username=username,
        email=email,
        cache_checked=cache_checked)
# Схемы данных Swagger
account_model = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'readOnly': True, 'example': 1},
        'username': {'type': 'string', 'minLength': 3, 'maxLength': 20, 'example': 'john_doe'},
        'email': {'type': 'string', 'format': 'email', 'example': 'user@example.com'},
        'about_me': {'type': 'string', 'example': 'Разработчик из Москвы', 'default': ''},
        'creation_method': {'type': 'string', 'enum': ['rest', 'soap', 'interface'], 'example': 'rest'}
    }
}

create_account_model = {
    'type': 'object',
    'required': ['username', 'email', 'password'],
    'properties': {
        'username': {'type': 'string', 'minLength': 3, 'maxLength': 20, 'example': 'jane_doe'},
        'email': {'type': 'string', 'format': 'email', 'example': 'user@example.com'},
        'password': {'type': 'string', 'minLength': 6, 'example': 'secret123'}
    }
}

update_username_model = {
    'type': 'object',
    'required': ['new_username'],
    'properties': {
        'new_username': {'type': 'string', 'minLength': 3, 'maxLength': 20, 'example': 'new_username123'}
    }
}

about_me_model = {
    'type': 'object',
    'required': ['about_me'],
    'properties': {
        'about_me': {'type': 'string', 'example': 'Люблю программирование и путешествия', 'maxLength': 500}
    }
}

holiday_model = {
    'type': 'object',
    'required': ['start_time', 'location', 'title'],
    'properties': {
        'id': {'type': 'integer', 'format': 'int64', 'readOnly': True, 'example': 42},
        'start_time': {'type': 'string', 'format': 'date-time', 'example': '2024-09-15T18:30:00Z'},
        'location': {'type': 'string', 'minLength': 3, 'maxLength': 255, 'example': 'Морковное поле №5'},
        'title': {'type': 'string', 'minLength': 3, 'maxLength': 100, 'example': 'Фестиваль весенней моркови'}
    }
}

swagger_config = {
    "headers": [],
    "specs": [{"endpoint": "apispec", "route": "/apispec.json"}],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "definitions": {
        "Account": account_model,
        "CreateAccount": create_account_model,
        "UpdateUsername": update_username_model,
        "AboutMe": about_me_model,
        "Holiday": holiday_model
    }
}
Swagger(app, config=swagger_config)

@app.route('/redis-edu')
def redis_education():
    """Образовательная страница Redis"""
    return render_template('redis_education.html')

@app.route('/redis-edu/init', methods=['POST'])
def edu_init_counter():
    """Инициализация счетчика"""
    try:
        app.redis.set('total_carrots', 0)
        return jsonify({'message': 'Счетчик инициализирован'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redis-edu/incr', methods=['POST'])
def edu_incr_counter():
    """Увеличение счетчика"""
    try:
        new_value = app.redis.incr('total_carrots')
        return jsonify({'value': new_value}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redis-edu/set-record', methods=['POST'])
def edu_set_record():
    """Установка рекорда"""
    try:
        app.redis.set('daily_record', 10)
        return jsonify({'message': 'Рекорд установлен'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redis-edu/get-counter', methods=['GET'])
def edu_get_counter():
    """Получение значения счетчика"""
    try:
        value = app.redis.get('total_carrots') or 0
        return jsonify({'value': int(value)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redis-edu/add-leaderboard', methods=['POST'])
def edu_add_leaderboard():
    """Добавление в рейтинг"""
    try:
        app.redis.zadd('top_users', {'Быстрый Заяц': 5})
        return jsonify({'message': 'Участник добавлен'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/redis-edu/get-leaderboard', methods=['GET'])
def edu_get_leaderboard():
    """Получение рейтинга"""
    try:
        leaderboard = []
        results = app.redis.zrange('top_users', 0, -1, withscores=True)
        for username, score in results:
            leaderboard.append({
                'username': username.decode('utf-8'),
                'score': int(score)
            })
        return jsonify({'leaderboard': leaderboard}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def validate_email(email):
    """Проверяет валидность email адреса"""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

@app.route('/profile/<int:user_id>')
def user_profile(user_id):
    """Страница профиля пользователя"""
    try:
        user = db_utils.get_account_by_id(user_id)
        if not user:
            abort(404)
        return render_template('profile.html', user=user)
    except Exception as e:
        abort(500, description="Ошибка базы данных")

@app.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        selected_table = request.args.get('table', 'accounts')
        
        with db_utils.get_db_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                tables = [row['table_name'] for row in cursor.fetchall()]
                
                if selected_table == 'accounts':
                    cursor.execute("SELECT * FROM accounts;")
                    data = cursor.fetchall()
                    sql_query = "SELECT * FROM accounts;"
                    
                elif selected_table == 'holidays':
                    cursor.execute("SELECT * FROM holidays ORDER BY start_time;")
                    data = cursor.fetchall()
                    sql_query = "SELECT * FROM holidays ORDER BY start_time;"
                    
                elif selected_table == 'user_holidays':
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
                    data = cursor.fetchall()
                    
                else:
                    data = []
                    sql_query = ""

        return render_template(
            'view_db.html',
            tables=tables,
            selected_table=selected_table,
            data=data,
            sql_query=sql_query.strip()
        )

    except Exception as e:
        app.logger.error(f"Database access error: {str(e)}")
        return render_template('error.html', error=str(e)), 500
        
@app.route('/accounts', methods=['GET'])
@swag_from({
    'tags': ['Accounts'],
    'responses': {
        200: {'description': 'Список всех учетных записей', 'schema': {'type': 'array', 'items': account_model}},
        500: {'description': 'Ошибка базы данных'}
    }
})
def get_accounts():
    """Получить всех зайцев"""
    try:
        accounts = db_utils.get_all_accounts()
        return jsonify(accounts), 200
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts', methods=['POST'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [{'name': 'body', 'in': 'body', 'required': True, 'schema': create_account_model}],
    'responses': {
        201: {'description': 'Созданная учетная запись', 'schema': account_model},
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
        return jsonify(validation_errors), 400
    
    try:
        new_user = db_utils.create_account(
            username=username,
            email=email,
            password=password,
            creation_method='rest'
        )
        return jsonify(new_user), 201

    except ValueError as e:
        error_msg = str(e)
        return jsonify({'error': error_msg}), 409
    
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
        
@app.route('/accounts/<int:user_id>', methods=['PUT'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True},
        {'name': 'body', 'in': 'body', 'required': True, 'schema': update_username_model}
    ],
    'responses': {
        200: {'description': 'Обновленные данные пользователя', 'schema': account_model},
        400: {'description': 'Некорректные данные'},
        404: {'description': 'Заяц не найден'},
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
        updated_user = db_utils.update_username(user_id, new_username)
        if not updated_user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(updated_user), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts/about/<int:user_id>', methods=['PUT'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True},
        {'name': 'about_me', 'in': 'body', 'required': True, 'schema': {'type': 'object', 'properties': {'about_me': {'type': 'string'}}}}
    ],
    'responses': {
        200: {'description': 'Обновленные данные пользователя', 'schema': account_model},
        404: {'description': 'Заяц не найден'}
    }
})
def update_about_me(user_id):
    """Обновить поле Любимые занятия"""
    data = request.get_json()
    about_me = data.get('about_me', '')
    
    try:
        updated_user = db_utils.update_about_me(user_id, about_me)
        if not updated_user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(updated_user), 200
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts/about/<int:user_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [{'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Информация "О себе" успешно удалена', 'schema': account_model},
        404: {'description': 'Заяц не найден'},
        500: {'description': 'Ошибка базы данных'}
    }
})
def delete_about_me(user_id):
    """Удалить информацию из поля любитмые занятия"""
    try:
        updated_user = db_utils.delete_about_me(user_id)
        if not updated_user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(updated_user), 200
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/accounts/<int:user_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [{'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Заяц успешно удален'},
        404: {'description': 'Заяц не найден'},
        500: {'description': 'Ошибка базы данных'}
    }
})
def delete_account(user_id):
    """Удалить зайца по ID"""
    try:
        success = db_utils.delete_account(user_id)
        if not success:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify({'message': 'Заяц успешно удален'}), 200
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

@app.route('/holidays', methods=['POST'])
@swag_from({
    'tags': ['Holidays'],
    'description': 'Создать новый праздник/мероприятие',
    'parameters': [{'name': 'body', 'in': 'body', 'required': True, 'schema': holiday_model}],
    'responses': {
        201: {'description': 'Праздник успешно создан', 'schema': holiday_model},
        400: {'description': 'Некорректные данные'},
        409: {'description': 'Конфликт данных'},
        500: {'description': 'Ошибка сервера'}
    }
})
def create_holiday():
    """Создать новый праздник"""
    data = request.get_json()
    
    required_fields = ['start_time', 'location', 'title']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({'error': f'Отсутствуют обязательные поля: {", ".join(missing_fields)}'}), 400
    
    errors = {}
    if len(data['title']) < 3 or len(data['title']) > 100:
        errors['title'] = 'Название должно быть от 3 до 100 символов'
    
    if len(data['location']) < 3 or len(data['location']) > 255:
        errors['location'] = 'Локация должна быть от 3 до 255 символов'
    
    try:
        datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
    except ValueError:
        errors['start_time'] = 'Некорректный формат даты. Используйте ISO 8601'
    
    if errors:
        return jsonify({'errors': errors}), 400
    
    try:
        new_holiday = db_utils.create_holiday(
            start_time=data['start_time'],
            location=data['location'],
            title=data['title']
        )
        return jsonify({
            'id': new_holiday['id'],
            'start_time': new_holiday['start_time'].isoformat() if isinstance(new_holiday['start_time'], datetime) else new_holiday['start_time'],
            'location': new_holiday['location'],
            'title': new_holiday['title']
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
        
@app.route('/holidays/<int:holiday_id>/attend', methods=['POST'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [
        {'name': 'holiday_id', 'in': 'path', 'required': True, 'type': 'integer', 'description': 'ID праздника'},
        {'name': 'body', 'in': 'body', 'required': True, 'schema': {'type': 'object', 'properties': {'user_id': {'type': 'integer'}}}}
    ],
    'responses': {
        201: {'description': 'Успешная запись', 'schema': {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'holiday': {'$ref': '#/definitions/Holiday'},
                'user': {'$ref': '#/definitions/Account'}
            }
        }},
        400: {'description': 'Некорректный запрос'}
    }
})
def add_user_to_holiday(holiday_id):
    """Записать зайца на праздник"""
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({'error': 'Необходимо указать user_id в теле запроса'}), 400
    
    user_id = data['user_id']

    try:
        # Проверка существования пользователя
        user = db_utils.get_account_by_id(user_id)
        if not user:
            return jsonify({'error': 'Заяц не найден'}), 404

        # Проверка существования праздника
        # В реальном приложении нужно добавить функцию get_holiday_by_id в db_utils
        with db_utils.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT title FROM holidays WHERE id = %s', (holiday_id,))
                holiday = cursor.fetchone()
                if not holiday:
                    return jsonify({'error': 'Праздник не найден'}), 404

        # Запись пользователя на праздник
        attendance = db_utils.add_user_to_holiday(user_id, holiday_id)
        
        return jsonify({
            'message': 'Заяц успешно записан на праздник',
            'holiday': {'id': holiday_id, 'title': holiday[0]},
            'user': {'id': user_id, 'username': user['username']},
            'attendance_id': attendance['id'],
            'created_at': attendance['created_at']
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500
        
@app.route('/holidays/<int:holiday_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'holiday_id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Праздник удален'},
        404: {'description': 'Праздник не найден'}
    }
})
def delete_holiday(holiday_id):
    """Удалить праздник"""
    try:
        success = db_utils.delete_holiday(holiday_id)
        if not success:
            return jsonify({'error': 'Holiday not found'}), 404
        return jsonify({'message': 'Holiday deleted'}), 200
    except Exception as e:
        return jsonify({'error': 'Database error'}), 500

@app.route('/holidays/<int:holiday_id>/attendees', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'holiday_id', 'in': 'path', 'type': 'integer', 'required': True, 'description': 'ID праздника'}],
    'responses': {
        200: {'description': 'Список участников праздника', 'schema': {'type': 'array', 'items': account_model}},
        404: {'description': 'Праздник не найден'}
    }
})
def get_holiday_attendees(holiday_id):
    """Получить список зайцев, идущих на праздник"""
    try:
        attendees = db_utils.get_holiday_attendees(holiday_id)
        return jsonify(attendees), 200
    except Exception as e:
        return jsonify({'error': 'Database error'}), 500

@app.route('/users/<int:user_id>/holidays', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True, 'description': 'ID пользователя'}],
    'responses': {
        200: {'description': 'Список праздников пользователя', 'schema': {'type': 'array', 'items': holiday_model}},
        404: {'description': 'Заяц не найден'}
    }
})
def get_user_holidays(user_id):
    """Получить список праздников, на которые записан заяц"""
    try:
        holidays = db_utils.get_user_holidays(user_id)
        return jsonify(holidays), 200
    except Exception as e:
        return jsonify({'error': 'Database error'}), 500

get_user_by_id_request_model = {
    'type': 'object',
    'required': ['id'],
    'properties': {'id': {'type': 'integer', 'description': 'ID зайца', 'example': 1}},
    'x-educational-purpose': 'Демонстрация нестандартного использования POST вместо GET'
}

swagger_config['definitions']['GetUserByIdRequest'] = get_user_by_id_request_model

@app.route('/accounts/get-by-id', methods=['POST'])
@swag_from({
    'tags': ['Accounts'],
    'description': 'Получить зайца по ID (POST вместо GET в учебных целях)',
    'parameters': [{'name': 'body', 'in': 'body', 'required': True, 'schema': {'$ref': '#/definitions/GetUserByIdRequest'}}],
    'responses': {
        200: {'description': 'Данные зайца', 'schema': account_model},
        400: {'description': 'Некорректный запрос'},
        404: {'description': 'Заяц не найден'}
    },
    'x-educational-note': 'Обычно для получения ресурса по ID используется GET-запрос. Этот POST-метод демонстрирует альтернативный подход.'
})
def get_user_by_id_post():
    """Получить зайца по ID (используя POST вместо GET)"""
    data = request.get_json()
    
    if not data or 'id' not in data:
        return jsonify({'error': 'Отсутствует обязательное поле: id'}), 400
    
    try:
        user_id = int(data['id'])
    except (TypeError, ValueError):
        return jsonify({'error': 'ID должен быть числом'}), 400
    
    try:
        user = db_utils.get_account_by_id(user_id)
        if not user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(user), 200
    except Exception as e:
        return jsonify({'error': 'Ошибка базы данных'}), 500

# SOAP сервис
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel, Array, Fault
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication

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
        try:
            user = db_utils.get_account_by_id(user_id)
            if not user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapUser(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                about_me=user['about_me'] or '',
                creation_method=user['creation_method']
            )
        except Exception as e:
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(_returns=Array(SoapUser))
    def get_all_users(ctx):
        try:
            users = db_utils.get_all_accounts()
            return [
                SoapUser(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    about_me=user['about_me'] or '',
                    creation_method=user['creation_method']
                )
                for user in users
            ]
        except Exception as e:
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')
    
    @rpc(SoapUserRequest, _returns=SoapResponse)
    def create_user(ctx, user_data):
        """Создать нового зайца"""
        try:
            # Логирование входящих данных
            app.logger.info(f"SOAP create_user request: "
                           f"username={user_data.username}, "
                           f"email={user_data.email}")
            
            new_user = db_utils.create_account(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,
                creation_method='soap',
                about_me=user_data.about_me
            )
            
            # Создаем объект SoapUser для ответа
            soap_user = SoapUser(
                id=new_user['id'],
                username=new_user['username'],
                email=new_user['email'],
                about_me=new_user['about_me'] or '',
                creation_method=new_user['creation_method']
            )
            
            # Формируем успешный ответ
            response = SoapResponse(
                status='success',
                message='User created successfully',
                user=soap_user
            )
            
            app.logger.info(f"User created successfully: ID={new_user['id']}")
            return response
            
        except ValueError as e:
            app.logger.error(f"ValueError in create_user: {str(e)}")
            return Fault(faultcode='Client', faultstring=str(e))
        except Exception as e:
            app.logger.error(f"Exception in create_user: {str(e)}")
            return Fault(faultcode='Server', faultstring=f'Internal server error: {str(e)}')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_username(ctx, user_id, new_username):
        """Обновить имя зайца"""
        try:
            updated_user = db_utils.update_username(user_id, new_username)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='Username updated',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except ValueError as e:
            raise Fault(faultcode='Client', faultstring=str(e))
        except Exception as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_about_me(ctx, user_id, about_text):
        """Обновить информацию в поле Любимые занятия"""
        try:
            updated_user = db_utils.update_about_me(user_id, about_text)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='About me updated',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except Exception as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_about_me(ctx, user_id):
        """Удалить информацию из поля Любимые занятия'"""
        try:
            updated_user = db_utils.delete_about_me(user_id)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='About me cleared',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except Exception as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_user(ctx, user_id):
        """Удалить зайца"""
        try:
            success = db_utils.delete_account(user_id)
            if not success:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='User deleted',
                user=None
            )
        except Exception as e:
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

@app.route('/search')
def search_page():
    return render_template('search_holidays.html')

@app.route('/api/search-holidays')
def api_search_holidays():
    sleep(3)
    search_query = request.args.get('query', '')
    try:
        results = db_utils.search_holidays(search_query)
        # Форматируем дату для вывода
        formatted_results = []
        for holiday in results:
            formatted_holiday = holiday.copy()
            # Если start_time - объект datetime, форматируем его
            if isinstance(holiday['start_time'], datetime):
                formatted_holiday['start_time'] = holiday['start_time'].strftime('%d.%m.%Y %H:%M')
            formatted_results.append(formatted_holiday)
        return jsonify(formatted_results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
import io
import csv
import zipfile
from datetime import datetime
from flask import make_response

def get_table_data(table_name):
    """Получение данных и заголовков таблицы"""
    with db_utils.get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            if table_name == 'accounts':
                cursor.execute("SELECT * FROM accounts;")
            elif table_name == 'holidays':
                cursor.execute("SELECT * FROM holidays;")
            elif table_name == 'user_holidays':
                cursor.execute("""
                    SELECT 
                        uh.id, uh.user_id, a.username AS user_name, 
                        uh.holiday_id, h.title AS holiday_title, uh.created_at
                    FROM user_holidays uh
                    LEFT JOIN accounts a ON uh.user_id = a.id
                    LEFT JOIN holidays h ON uh.holiday_id = h.id;
                """)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
    return data, columns

def format_value(value):
    """Форматирование значений для CSV"""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value) if value is not None else ''

@app.route('/export-db')
def export_database():
    """Выгрузка текущей таблицы в CSV"""
    table = request.args.get('table', 'accounts')
    data, headers = get_table_data(table)
    
    # Формируем CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    
    for row in data:
        writer.writerow([format_value(value) for value in row])
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={table}.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8"
    return response

@app.route('/export-db-all')
def export_all_database():
    """Выгрузка всей БД в ZIP с CSV"""
    buffer = io.BytesIO()
    tables = ['accounts', 'holidays', 'user_holidays']
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for table in tables:
            data, headers = get_table_data(table)
            
            # Формируем CSV для таблицы
            csv_output = io.StringIO()
            writer = csv.writer(csv_output, delimiter=';')
            writer.writerow(headers)
            for row in data:
                writer.writerow([format_value(value) for value in row])
                
            zip_file.writestr(f"{table}.csv", csv_output.getvalue())
    
    buffer.seek(0)
    response = make_response(buffer.read())
    response.headers["Content-Disposition"] = "attachment; filename=database_export.zip"
    response.headers["Content-type"] = "application/zip"
    return response
# Добавим импорт
from werkzeug.security import check_password_hash

# Добавим новый маршрут для пайплайна


# Добавим функцию проверки учетной записи
@app.route('/verify-account', methods=['POST'])
def verify_account():
    username = request.form.get('username')
    password = request.form.get('password')
    error = None
    success = None
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Находим пользователя
            cursor.execute(
                'SELECT password_hash FROM accounts WHERE username = %s',
                (username,)
            )
            user = cursor.fetchone()
            
            if user is None:
                error = "Пользователь не найден"
            elif not check_password_hash(user[0], password):
                error = "Неверный пароль"
            else:
                success = "Учетная запись успешно проверена! ✅"
                
    except Exception as e:
        error = f"Ошибка базы данных: {str(e)}"
    finally:
        conn.close()
    
    return render_template(
        'pipeline.html', 
        error=error, 
        success=success
    )
if __name__ == '__main__':
    db_utils.init_db()
    app.run()
