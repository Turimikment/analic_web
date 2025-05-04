from flask import Flask, render_template
from flask_restx import Api, Resource, fields, reqparse
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# ... (остальной импорт из предыдущего кода) ...

app = Flask(__name__)
@app.route('/')
def home():
    return render_template('index.html')

app.config['DATABASE'] = 'accounts.db'
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['ERROR_404_HELP'] = False

api = Api(
    app,
    version='1.0',
    title='Account API',
    description='API для управления пользователями',
    doc='/swagger/',
    default='Основные операции',
    default_label='Операции с аккаунтами',
    swagger_ui_params={
        "docExpansion": "full",
        "deepLinking": True,
        "displayOperationId": False,
        "showExtensions": True,
        "defaultModelsExpandDepth": -1  # Скрыть модели схем
    }
)

# Модели для Swagger
account_model = api.model('Account', {
    'id': fields.Integer(readonly=True),
    'username': fields.String(required=True),
    'email': fields.String(required=True),
    'about_me': fields.String(description='Информация о пользователе')
})

create_account_model = api.model('CreateAccount', {
    'username': fields.String(required=True, description='Имя пользователя (3-20 символов)'),
    'email': fields.String(required=True, description= ''' Валидный email-адрес. Требования:
        - Должен содержать @
        - Локальная часть (до @) может включать: 
          буквы, цифры, . ! # $ % & ' * + - / = ? ^ _ ` { | } ~
        - Доменная часть (после @) должна содержать:
          минимум одну точку, буквы/цифры и дефисы между частями
        Примеры: 
        - user@example.com 
        - john.doe123@sub.domain.com'''),
    'password': fields.String(required=True, description='Пароль (минимум 6 символов)')
})

# Парсер запросов
parser = reqparse.RequestParser()
parser.add_argument('username', type=str, required=True, help='Имя пользователя обязательно')
parser.add_argument('email', type=str, required=True, help='Email обязателен')
parser.add_argument('password', type=str, required=True, help='Пароль обязателен')

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

@api.route('/accounts')
class AccountsResource(Resource):
    @api.doc('list_accounts')
    @api.marshal_list_with(account_model)
    def get(self):
        """Получить все учетные записи"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, username, email,  about_me 
                    FROM accounts
                ''')
                return [dict(row) for row in cursor.fetchall()], 200
        except sqlite3.Error as e:
            api.abort(500, 'Ошибка базы данных')

    @api.doc('create_account')
    @api.expect(create_account_model)
    @api.marshal_with(account_model, code=201)
    @api.response(400, 'Некорректные данные')
    @api.response(409, 'Конфликт данных')
    def post(self):
        """Создать новую учетную запись"""
        args = parser.parse_args()
        
        # Валидация данных
        errors = {}
        
        # Проверка имени пользователя
        if len(args['username']) < 3 or len(args['username']) > 20:
            errors['username'] = 'Длина имени пользователя должна быть от 3 до 20 символов'
        
        # Проверка email
        if not validate_email(args['email']):
            errors['email'] = 'Некорректный формат email'
        
        # Проверка пароля
        if len(args['password']) < 6:
            errors['password'] = 'Пароль должен содержать минимум 6 символов'
        
        if errors:
            api.abort(400, errors)
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                password_hash = generate_password_hash(args['password'])
                
                cursor.execute('''
                    INSERT INTO accounts (username, email, password_hash)
                    VALUES (?, ?, ?)
                ''', (args['username'], args['email'], password_hash))
                
                conn.commit()
                sleep(0.1)
                
                # Получаем созданную запись
                cursor.execute('''
                    SELECT id, username, email 
                    FROM accounts
                    WHERE id = ? 
                ''',(cursor.lastrowid ,))
            
                new_account = cursor.fetchall()
                print(new_account)
                return  new_account, 200
                
        except sqlite3.IntegrityError as e:
            error_msg = 'Ошибка уникальности: '
            if 'username' in str(e):
                error_msg += 'Имя пользователя уже существует'
            elif 'email' in str(e):
                error_msg += 'Email уже зарегистрирован'
            api.abort(409, error_msg)

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

    @app.route('/profile/<int:user_id>')
    def user_profile(user_id):
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
                return render_template('404.html'), 404
            
            return render_template('profile.html', user=dict(user))

update_username_model = api.model('UpdateUsername', {
    'new_username': fields.String(
        required=True, 
        min_length=3, 
        max_length=20,
        description='Новое имя пользователя (3-20 символов)'
    )
})

@api.route('/accounts/<int:user_id>')
@api.doc(params={'user_id': 'ID пользователя'})
class AccountResource(Resource):
    @api.doc('update_username')
    @api.expect(update_username_model)
    @api.marshal_with(account_model)
    @api.response(400, 'Некорректные данные')
    @api.response(404, 'Пользователь не найден')
    @api.response(409, 'Имя пользователя уже занято')
    def put(self, user_id):
        """Обновить кличку зайца"""
        data = api.payload
        new_username = data.get('new_username', '').strip()
        
        # Валидация данных
        if not new_username:
            api.abort(400, 'Имя пользователя не может быть пустым')
        if len(new_username) < 3:
            api.abort(400, 'Имя пользователя должно содержать минимум 3 символа')
            
        try:
            with sqlite3.connect(app.config['DATABASE']) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Проверка существования пользователя
                cursor.execute('SELECT id FROM accounts WHERE id = ?', (user_id,))
                if not cursor.fetchone():
                    api.abort(404, 'Пользователь не найден')
                
                # Проверка уникальности нового имени
                cursor.execute('SELECT id FROM accounts WHERE username = ? AND id != ?', 
                             (new_username, user_id))
                if cursor.fetchone():
                    api.abort(409, 'Имя пользователя уже занято')
                
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
                
                result = cursor.fetchone()
                return dict(result) if result else api.abort(404, 'Пользователь не найден')
                
        except sqlite3.Error as e:
            app.logger.error(f'Database error: {str(e)}')
            api.abort(500, 'Ошибка базы данных')
        except Exception as e:
            app.logger.error(f'Unexpected error: {str(e)}')
            api.abort(500, 'Внутренняя ошибка сервера')

    @api.route('/accounts/<int:user_id>/about')
    @api.doc(params={'user_id': 'ID пользователя'})
    class AboutMeResource(Resource):
        @api.doc('update_about_me')
        @api.expect(api.model('AboutMeUpdate', {'about_me': fields.String}))
        @api.marshal_with(account_model)
        def put(self, user_id):
            """Обновить информацию 'О себе'"""
            data = api.payload
            about_me = data.get('about_me', '')
        
            try:
                with sqlite3.connect(app.config['DATABASE']) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                
                    # Обновление информации
                    cursor.execute('''
                        UPDATE accounts 
                        SET about_me = ?
                        WHERE id = ?
                    ''', (about_me, user_id))
                
                # Проверка количества измененных строк
                    if cursor.rowcount == 0:
                        api.abort(404, 'Пользователь не найден')
                
                    conn.commit()
                
                # Получение обновленных данных
                    cursor.execute('''
                        SELECT id, username, email, about_me 
                        FROM accounts 
                        WHERE id = ?
                    ''', (user_id,))
                
                    result = cursor.fetchone()
                    return dict(result)
                
            except sqlite3.Error as e:
                app.logger.error(f'Ошибка базы данных: {str(e)}')
                api.abort(500, 'Ошибка сервера')
            except Exception as e:
                app.logger.error(f'Непредвиденная ошибка: {str(e)}')
                api.abort(500, 'Внутренняя ошибка сервера')

     
        @api.doc(params={'user_id': 'ID пользователя'})
        @api.marshal_with(account_model)
        def get(self, user_id):  # GET-метод
            """Получить информацию о пользователе по ID"""
            try:
                with sqlite3.connect(app.config['DATABASE']) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Выполняем параметризованный запрос
                    cursor.execute('''
                        SELECT id, username, email, about_me 
                        FROM accounts 
                        WHERE id = ?
                    ''', (user_id,))
                    
                    user = cursor.fetchone()
                    
                    if not user:
                        api.abort(404, 'Пользователь не найден')
                        
                    return dict(user)
                    
            except sqlite3.Error as e:
                app.logger.error(f"Ошибка базы данных: {str(e)}")
                api.abort(500, 'Ошибка сервера')
            except Exception as e:
                app.logger.error(f"Непредвиденная ошибка: {str(e)}")
                api.abort(500, 'Внутренняя ошибка сервера')



        @api.doc('delete_about_me')
        def delete(self, user_id):
            """Удалить информацию 'О себе'"""
            with sqlite3.connect(app.config['DATABASE']) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accounts 
                    SET about_me = '' 
                    WHERE id = ?
                ''', (user_id,))
                conn.commit()
                return {'message': 'Информация удалена'}

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
