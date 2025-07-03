 
import re
from datetime import datetime
from werkzeug.security import check_password_hash
from .db_utils import get_db_connection

def validate_email(email: str) -> bool:
    """Проверяет валидность email адреса"""
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def validate_username(username: str) -> bool:
    """Проверяет имя пользователя"""
    return 3 <= len(username) <= 20

def validate_password(password: str) -> bool:
    """Проверяет пароль"""
    return len(password) >= 6

def validate_about_me(text: str) -> bool:
    """Проверяет поле 'О себе'"""
    return len(text) <= 500  # Максимум 500 символов

def validate_holiday_title(title: str) -> bool:
    """Проверяет название праздника"""
    return 3 <= len(title) <= 100

def validate_holiday_location(location: str) -> bool:
    """Проверяет локацию праздника"""
    return 3 <= len(location) <= 255

def validate_datetime(dt_str: str) -> bool:
    """Проверяет формат даты и времени"""
    try:
        datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return True
    except (ValueError, TypeError):
        return False

def authenticate_user(username: str, password: str) -> bool:
    """Аутентифицирует пользователя"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT password_hash FROM accounts WHERE username = %s',
                (username,)
            )
            user = cursor.fetchone()
            
            if user and check_password_hash(user[0], password):
                return True
        return False
    except Exception as e:
        print(f"Authentication error: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def validate_user_credentials(username: str, password: str) -> dict:
    """Проверяет учетные данные и возвращает ошибки"""
    errors = {}
    
    if not validate_username(username):
        errors['username'] = 'Имя пользователя должно быть от 3 до 20 символов'
    
    if not validate_password(password):
        errors['password'] = 'Пароль должен быть не менее 6 символов'
    
    if not errors and not authenticate_user(username, password):
        errors['auth'] = 'Неверное имя пользователя или пароль'
    
    return errors

def validate_account_data(data: dict) -> dict:
    """Валидирует данные для создания/обновления аккаунта"""
    errors = {}
    
    if 'username' in data:
        if not validate_username(data['username']):
            errors['username'] = 'Имя пользователя должно быть от 3 до 20 символов'
    
    if 'email' in data:
        if not validate_email(data['email']):
            errors['email'] = 'Некорректный формат email'
    
    if 'password' in data:
        if not validate_password(data['password']):
            errors['password'] = 'Пароль должен быть не менее 6 символов'
    
    if 'about_me' in data:
        if not validate_about_me(data['about_me']):
            errors['about_me'] = 'Поле "О себе" не должно превышать 500 символов'
    
    return errors

def validate_holiday_data(data: dict) -> dict:
    """Валидирует данные для создания праздника"""
    errors = {}
    required_fields = ['start_time', 'location', 'title']
    
    for field in required_fields:
        if field not in data:
            errors[field] = f'Поле {field} обязательно для заполнения'
    
    if 'title' in data and not validate_holiday_title(data['title']):
        errors['title'] = 'Название должно быть от 3 до 100 символов'
    
    if 'location' in data and not validate_holiday_location(data['location']):
        errors['location'] = 'Локация должна быть от 3 до 255 символов'
    
    if 'start_time' in data and not validate_datetime(data['start_time']):
        errors['start_time'] = 'Некорректный формат даты. Используйте ISO 8601'
    
    return errors