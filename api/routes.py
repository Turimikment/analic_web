 # app/api/routes.py
from flask import Blueprint, request, jsonify
from flasgger import swag_from
from utils import db_utils
from utils.validation import (
    validate_account_data,
    validate_holiday_data,
    validate_email,
    validate_username
)
from datetime import datetime
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Модели для Swagger
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

# Регистрация моделей в Swagger
def register_swagger_models(spec):
    spec.definition('Account', schema=account_model)
    spec.definition('CreateAccount', schema=create_account_model)
    spec.definition('UpdateUsername', schema=update_username_model)
    spec.definition('AboutMe', schema=about_me_model)
    spec.definition('Holiday', schema=holiday_model)

# Роуты для работы с аккаунтами
@api_bp.route('/accounts', methods=['GET'])
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
        logger.error(f"Database error in get_accounts: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/accounts', methods=['POST'])
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
    errors = validate_account_data(data)
    
    if errors:
        return jsonify(errors), 400
    
    try:
        new_user = db_utils.create_account(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            creation_method='rest'
        )
        return jsonify(new_user), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.error(f"Error creating account: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/accounts/<int:user_id>', methods=['PUT'])
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
    """Обновить имя зайца"""
    data = request.get_json()
    new_username = data.get('new_username', '').strip()
    
    if not validate_username(new_username):
        return jsonify({'error': 'Некорректное имя пользователя'}), 400
    
    try:
        updated_user = db_utils.update_username(user_id, new_username)
        if not updated_user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(updated_user), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        logger.error(f"Error updating username: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/accounts/about/<int:user_id>', methods=['PUT'])
@swag_from({
    'tags': ['Accounts'],
    'parameters': [
        {'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True},
        {'name': 'about_me', 'in': 'body', 'required': True, 'schema': {'type': 'object', 'properties': {'about_me': {'type': 'string'}}}}
    ],
    'responses': {
        200: {'description': 'Обновленные данные пользователя', 'schema': account_model},
        404: {'description': 'Заяц не найден'},
        500: {'description': 'Ошибка базы данных'}
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
        logger.error(f"Error updating about_me: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/accounts/about/<int:user_id>', methods=['DELETE'])
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
    """Удалить информацию из поля любимые занятия"""
    try:
        updated_user = db_utils.delete_about_me(user_id)
        if not updated_user:
            return jsonify({'error': 'Заяц не найден'}), 404
        return jsonify(updated_user), 200
    except Exception as e:
        logger.error(f"Error deleting about_me: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/accounts/<int:user_id>', methods=['DELETE'])
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
        logger.error(f"Error deleting account: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

# Роуты для работы с праздниками
@api_bp.route('/holidays', methods=['POST'])
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
    errors = validate_holiday_data(data)
    
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
        logger.error(f"Error creating holiday: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/holidays/<int:holiday_id>/attend', methods=['POST'])
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
        400: {'description': 'Некорректный запрос'},
        404: {'description': 'Пользователь или праздник не найден'},
        409: {'description': 'Пользователь уже записан на праздник'},
        500: {'description': 'Ошибка сервера'}
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
        logger.error(f"Error adding user to holiday: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

@api_bp.route('/holidays/<int:holiday_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'holiday_id', 'in': 'path', 'type': 'integer', 'required': True}],
    'responses': {
        200: {'description': 'Праздник удален'},
        404: {'description': 'Праздник не найден'},
        500: {'description': 'Ошибка сервера'}
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
        logger.error(f"Error deleting holiday: {str(e)}")
        return jsonify({'error': 'Database error'}), 500

@api_bp.route('/holidays/<int:holiday_id>/attendees', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'holiday_id', 'in': 'path', 'type': 'integer', 'required': True, 'description': 'ID праздника'}],
    'responses': {
        200: {'description': 'Список участников праздника', 'schema': {'type': 'array', 'items': account_model}},
        404: {'description': 'Праздник не найден'},
        500: {'description': 'Ошибка сервера'}
    }
})
def get_holiday_attendees(holiday_id):
    """Получить список зайцев, идущих на праздник"""
    try:
        attendees = db_utils.get_holiday_attendees(holiday_id)
        return jsonify(attendees), 200
    except Exception as e:
        logger.error(f"Error getting attendees: {str(e)}")
        return jsonify({'error': 'Database error'}), 500

@api_bp.route('/users/<int:user_id>/holidays', methods=['GET'])
@swag_from({
    'tags': ['Holidays'],
    'parameters': [{'name': 'user_id', 'in': 'path', 'type': 'integer', 'required': True, 'description': 'ID пользователя'}],
    'responses': {
        200: {'description': 'Список праздников пользователя', 'schema': {'type': 'array', 'items': holiday_model}},
        404: {'description': 'Заяц не найден'},
        500: {'description': 'Ошибка сервера'}
    }
})
def get_user_holidays(user_id):
    """Получить список праздников, на которые записан заяц"""
    try:
        holidays = db_utils.get_user_holidays(user_id)
        return jsonify(holidays), 200
    except Exception as e:
        logger.error(f"Error getting user holidays: {str(e)}")
        return jsonify({'error': 'Database error'}), 500

# Специальный роут для демонстрации POST вместо GET
get_user_by_id_request_model = {
    'type': 'object',
    'required': ['id'],
    'properties': {'id': {'type': 'integer', 'description': 'ID зайца', 'example': 1}},
    'x-educational-purpose': 'Демонстрация нестандартного использования POST вместо GET'
}

@api_bp.route('/accounts/get-by-id', methods=['POST'])
@swag_from({
    'tags': ['Accounts'],
    'description': 'Получить зайца по ID (POST вместо GET в учебных целях)',
    'parameters': [{'name': 'body', 'in': 'body', 'required': True, 'schema': get_user_by_id_request_model}],
    'responses': {
        200: {'description': 'Данные зайца', 'schema': account_model},
        400: {'description': 'Некорректный запрос'},
        404: {'description': 'Заяц не найден'},
        500: {'description': 'Ошибка сервера'}
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
        logger.error(f"Error getting user by ID: {str(e)}")
        return jsonify({'error': 'Ошибка базы данных'}), 500

# Роут для поиска праздников
@api_bp.route('/search-holidays', methods=['GET'])
@swag_from({
    'tags': ['Search'],
    'parameters': [
        {'name': 'query', 'in': 'query', 'type': 'string', 'description': 'Поисковый запрос'},
        {'name': 'use_cache', 'in': 'query', 'type': 'boolean', 'description': 'Использовать кэширование'}
    ],
    'responses': {
        200: {'description': 'Результаты поиска', 'schema': {'type': 'array', 'items': holiday_model}},
        500: {'description': 'Ошибка сервера'}
    }
})
def api_search_holidays():
    """Поиск праздников по названию или месту проведения"""
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
        logger.error(f"Error searching holidays: {str(e)}")
        return jsonify({'error': str(e)}), 500
