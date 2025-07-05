# app/main/routes.py
import functools
from flask import Blueprint, render_template, redirect, url_for, request, session
from utils import db_utils
from utils.validation import validate_email
from werkzeug.security import check_password_hash, generate_password_hash
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

# Декоратор для проверки авторизации
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    """Стартовая страница входа"""
    return render_template('index.html')
@main_bp.route('/base.html')
def heap():
    return render_template('base.html')

@main_bp.route('/login', methods=['POST'])
def login():
    """Обработка входа пользователя"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    try:
        conn = db_utils.get_db_connection()
        with conn.cursor() as cursor:
            # Находим пользователя
            cursor.execute(
                'SELECT id, password_hash FROM accounts WHERE username = %s',
                (username,)
            )
            user = cursor.fetchone()
            
            if user is None:
                return render_template('index.html', error='Пользователь не найден')
            
            # Проверяем пароль
            if check_password_hash(user[1], password):
                session['logged_in'] = True
                session['user_id'] = user[0]
                session['username'] = username
                return redirect(url_for('main.home'))
            else:
                return render_template('index.html', error='Неверный пароль')
                
    except Exception as e:
        logger.error(f"Ошибка входа: {str(e)}")
        return render_template('index.html', error='Ошибка базы данных')
    finally:
        conn.close()

@main_bp.route('/logout')
def logout():
    """Выход пользователя из системы"""
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('main.index'))

@main_bp.route('/home')
@login_required
def home():
    """Домашняя страница после входа"""
    return render_template('home.html', username=session['username'])

@main_bp.route('/pipeline')
@login_required
def pipeline():
    """Страница пайплайна обучения"""
    return render_template('pipeline.html')

@main_bp.route('/redis-stats')
@login_required
def redis_stats_page():
    """Страница статистики Redis"""
    return render_template('redis_stats.html')

@main_bp.route('/soap-interface')
@login_required
def soap_interface():
    """Страница SOAP-интерфейса"""
    return render_template('soap.html')

@main_bp.route('/profile/<int:user_id>')
@login_required
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
@login_required
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


