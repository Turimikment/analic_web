# app/main/routes.py
from flask import Blueprint, render_template, redirect, url_for, request
from utils import db_utils
from utils.validation import validate_email
from werkzeug.security import check_password_hash
import logging
from flask import session, redirect, url_for
# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Домашняя страница с приветствием"""
    return render_template('index.html')

@main_bp.route('/home')
def home():
    """Домашняя страница с приветствием"""
    return render_template('home.html')

@main_bp.route('/main')
def main_page():
    """Главная страница портала"""
    return render_template('base.html')

@main_bp.route('/pipeline')
def pipeline():
    """Страница пайплайна обучения"""
    return render_template('pipeline.html')

@main_bp.route('/redis-stats')
def redis_stats_page():
    """Страница статистики Redis"""
    return render_template('redis_stats.html')


@main_bp.route('/soap-interface')
def soap_interface():
    """Страница SOAP-интерфейса"""
    return render_template('soap.html')

@main_bp.route('/profile/<int:user_id>')
def user_profile(user_id):
    """Страница профиля пользователя"""
    try:
        user = db_utils.get_account_by_id(user_id)
        if not user:
            return render_template('404.html'), 404
        return render_template('profile.html', user=user)
    except Exception as e:
        logger.error(f"Database error: {e}")
        return render_template('error.html', error="Ошибка базы данных"), 500

@main_bp.route('/create-user', methods=['GET', 'POST'])
def create_user():
    """Страница создания пользователя"""
    form_errors = {}
    username = ''
    email = ''
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
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
                return redirect(url_for('main.pipeline'))
                
            except ValueError as e:
                form_errors['database'] = str(e)
            except Exception as e:
                logger.error(f"Database error: {e}")
                form_errors['database'] = f'Ошибка базы данных: {str(e)}'
    
    # Для GET-запросов и POST с ошибками
    return render_template('create_user.html',
        errors=form_errors,
        username=username,
        email=email)


@main_bp.route('/verify-account', methods=['POST'])
def verify_account():
    """Проверка учетной записи пользователя"""
    username = request.form.get('username')
    password = request.form.get('password')
    error = None
    success = None
    
    try:
        conn = db_utils.get_db_connection()
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
        logger.error(f"Database error: {e}")
        error = f"Ошибка базы данных: {str(e)}"
    finally:
        conn.close()
    
    return render_template(
        'pipeline.html', 
        error=error, 
        success=success
    )
def validate_credentials(username, password):
    """Проверяет правильность учетных данных пользователя"""
    try:
        conn = db_utils.get_db_connection()
        with conn.cursor() as cursor:
            # Находим пользователя
            cursor.execute(
                'SELECT password_hash FROM accounts WHERE username = %s',
                (username,)
            )
            user = cursor.fetchone()
            
            if user is None:
                return False  # Пользователь не найден
                
            # Сравниваем хеш пароля
            if check_password_hash(user[0], password):
                return True  # Пароль верный
                
            return False  # Неверный пароль
                
    except Exception as e:
        logger.error(f"Ошибка проверки учетных данных: {str(e)}")
        return False
    finally:
        conn.close()

@main_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Проверка учетных данных
    if validate_credentials(username, password):
        session['username'] = username
        session['logged_in'] = True
        return redirect(url_for('main.welcome'))
    else:
        return render_template('index.html', error='Неверные учетные данные')

@main_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('main.index'))

@main_bp.route('/welcome')
def welcome():
    if not session.get('logged_in'):
        return redirect(url_for('main.index'))
    return render_template('welcome.html', username=session['username'])