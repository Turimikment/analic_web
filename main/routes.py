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

@main_bp.route('/docs')
@login_required
def docs():
    """Страница с документацией по АПИ"""
    return render_template('docs.html')

@main_bp.route('/docs/kafka')
@login_required
def kafka_docs():
    """Страница с документацией по Kafka тренажёру и Kafka UI"""
    return render_template('kafka_docs.html')

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
def create_user():
    """Страница создания пользователя"""
    form_errors = {}
    username = ''
    email = ''
    conn = None  # Инициализируем соединение как None
    
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
                # Устанавливаем соединение только при необходимости
                conn = db_utils.get_db_connection()
                with conn.cursor() as cursor:
                    # Проверяем уникальность имени пользователя и email
                    cursor.execute(
                        "SELECT id FROM accounts WHERE username = %s OR email = %s",
                        (username, email)
                    )
                    existing_user = cursor.fetchone()
                    
                    if existing_user:
                        form_errors['database'] = "Пользователь с таким именем или email уже существует"
                    else:
                        # Хешируем пароль
                        password_hash = generate_password_hash(password)
                        
                        # Создаем нового пользователя
                        cursor.execute(
                            "INSERT INTO accounts (username, email, password_hash, creation_method) "
                            "VALUES (%s, %s, %s, 'interface') RETURNING id",
                            (username, email, password_hash)
                        )
                        new_user_id = cursor.fetchone()[0]
                        conn.commit()
                        
                        # После успешного создания перенаправляем на страницу входа
                        return redirect(url_for('main.index'))
                
            except Exception as e:
                logger.error(f"Database error: {e}")
                form_errors['database'] = f'Ошибка базы данных: {str(e)}'
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()
    
    # Для GET-запросов и POST с ошибками
    return render_template('create_user.html',
        errors=form_errors,
        username=username,
        email=email)
@main_bp.route('/base')
@login_required
def heap():
    """Доступ к песочнице"""
    progress = db_utils.check_user_progress(session['user_id'])
    
    # Проверяем, выполнены ли все задачи или аккаунт создан не через интерфейс
    if progress and (progress[3] or (progress[0] and progress[1] and progress[2])):
        return render_template('base.html')
    else:
        return render_template('access_denied.html')
    
@main_bp.route('/verify-user-id', methods=['POST'])
@login_required
def verify_user_id():
    """Проверка выполнения REST задания (поиск ID через Swagger)"""
    try:
        user_id = session['user_id']
        entered_id = request.form.get('user_id', '').strip()
        
        # Проверяем, совпадает ли введенный ID с ID пользователя
        if entered_id == str(user_id):
            # Обновляем прогресс пользователя
            conn = db_utils.get_db_connection()
            try:
                with conn.cursor() as cursor:
                    # Проверяем, существует ли запись прогресса
                    cursor.execute(
                        "SELECT user_id FROM user_progress WHERE user_id = %s",
                        (user_id,)
                    )
                    if not cursor.fetchone():
                        # Создаем запись, если ее нет
                        cursor.execute(
                            "INSERT INTO user_progress (user_id) VALUES (%s)",
                            (user_id,)
                        )
                    
                    # Обновляем прогресс (отмечаем выполнение REST задания)
                    cursor.execute(
                        "UPDATE user_progress SET task1 = TRUE "
                        "WHERE user_id = %s",
                        (user_id,)
                    )
                    conn.commit()
            except Exception as e:
                logger.error(f"Database error in verify_user_id: {str(e)}")
                return redirect(url_for('main.rest_task', error="Ошибка базы данных"))
            finally:
                conn.close()
            
            # Перенаправляем на страницу REST задания с сообщением об успехе
            return redirect(url_for('main.rest_task', success="✅ Задание выполнено успешно!"))
        else:
            return redirect(url_for('main.rest_task', error="⚠️ Неверный ID. Попробуйте еще раз"))
    
    except KeyError:
        # Если нет user_id в сессии
        return redirect(url_for('main.index'))
    except Exception as e:
        logger.error(f"Unexpected error in verify_user_id: {str(e)}")
        return redirect(url_for('main.rest_task', error="Произошла непредвиденная ошибка"))
    
@main_bp.route('/course')
@login_required
def course():
    """Страница обучающего курса"""
    return render_template('course.html')

@main_bp.route('/course/rest')
@login_required
def rest_task():
    """Страница REST задания"""
    progress = db_utils.check_user_progress(session['user_id'])
    return render_template('rest_task.html', 
                         task_error=request.args.get('error'),
                         task_success=request.args.get('success'),
                         completed=progress[0] if progress else False)

@main_bp.route('/course/soap')
@login_required
def soap_task():
    """Страница SOAP задания"""
    progress = db_utils.check_user_progress(session['user_id'])
    return render_template('soap_task.html',
                         error=request.args.get('error'),
                         success=request.args.get('success'),
                         completed=progress[1] if progress else False)

@main_bp.route('/course/db')
@login_required
def db_task():
    """Страница задания с БД"""
    progress = db_utils.check_user_progress(session['user_id'])
    return render_template('db_task.html',
                         error=request.args.get('error'),
                         success=request.args.get('success'),
                         completed=progress[2] if progress else False)


@main_bp.route('/verify-soap-task', methods=['POST'])
@login_required
def verify_soap_task():
    """Проверка выполнения SOAP задания"""
    try:
        user_id = session['user_id']
        user = db_utils.get_account_by_id(user_id)
        
        if user and user.get('about_me'):
            # Отмечаем выполнение задания
            conn = db_utils.get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_progress SET task2 = TRUE WHERE user_id = %s",
                    (user_id,)
                )
                conn.commit()
            return redirect(url_for('main.soap_task', success="✅ Задание выполнено успешно!"))
        else:
            return redirect(url_for('main.soap_task', error="⚠️ Поле 'О себе' пустое. Выполните задание через SoapUI."))
    
    except Exception as e:
        logger.error(f"Ошибка проверки SOAP задания: {str(e)}")
        return redirect(url_for('main.soap_task', error="Произошла ошибка при проверке"))   
    
@main_bp.route('/verify-db-task', methods=['POST'])
@login_required
def verify_db_task():
    """Проверка выполнения задания с БД"""
    try:
        user_id = session['user_id']
        entered_hash = request.form.get('password_hash', '').strip()
        
        # Получаем настоящий хэш из базы данных
        conn = db_utils.get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM accounts WHERE id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            
            if result and result[0] == entered_hash:
                # Отмечаем выполнение задания
                cursor.execute(
                    "UPDATE user_progress SET task3 = TRUE WHERE user_id = %s",
                    (user_id,)
                )
                conn.commit()
                return redirect(url_for('main.db_task', success="✅ Задание выполнено успешно!"))
            else:
                return redirect(url_for('main.db_task', error="⚠️ Неверный hash. Проверьте, что скопировали правильное значение."))
    
    except Exception as e:
        logger.error(f"Ошибка проверки задания с БД: {str(e)}")
        return redirect(url_for('main.db_task', error="Произошла ошибка при проверке"))