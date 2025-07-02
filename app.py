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
from .routes import  main_routes
from .routes import admin_routes
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
app.register_blueprint(admin_routes.admin_bp)
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

from spyne.server.wsgi import WsgiApplication
from soap_service import soap_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/soap': WsgiApplication(soap_app)
})


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
