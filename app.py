from flask import Flask, render_template
from flask_restx import Api, Resource, fields, reqparse
import psycopg2
from psycopg2.extras import DictCursor
import re
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from time import sleep
import os

app = Flask(__name__)
@app.route('/')
def home():
    return render_template('index.html')

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
        "defaultModelsExpandDepth": -1
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
    'email': fields.String(required=True, description='Валидный email-адрес'),
    'password': fields.String(required=True, description='Пароль (минимум 6 символов)')
})

parser = reqparse.RequestParser()
parser.add_argument('username', type=str, required=True, help='Имя пользователя обязательно')
parser.add_argument('email', type=str, required=True, help='Email обязателен')
parser.add_argument('password', type=str, required=True, help='Пароль обязателен')
def get_db():
    try:
        return psycopg2.connect(
            os.environ.get('postgresql://db_analitick_veb_user:qtUD994hJSlRfZ79F95fZMDajBKOuVuo@dpg-d09ln50gjchc7398l9bg-a.oregon-postgres.render.com/db_analitick_veb'),
            sslmode='require'
        )
    except psycopg2.OperationalError as e:
        print(f"Connection failed: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise
def init_db():
    """Инициализация базы данных"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            about_me TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

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
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, email, about_me FROM accounts')
            result = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            return result, 200
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

    @api.doc('create_account')
    @api.expect(create_account_model)
    @api.marshal_with(account_model, code=201)
    @api.response(400, 'Некорректные данные')
    @api.response(409, 'Конфликт данных')
    def post(self):
        """Создать новую учетную запись"""
        args = parser.parse_args()
        
        errors = {}
        if len(args['username']) < 3 or len(args['username']) > 20:
            errors['username'] = 'Длина имени пользователя должна быть от 3 до 20 символов'
        
        if not validate_email(args['email']):
            errors['email'] = 'Некорректный формат email'
        
        if len(args['password']) < 6:
            errors['password'] = 'Пароль должен содержать минимум 6 символов'
        
        if errors:
            api.abort(400, errors)
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            password_hash = generate_password_hash(args['password'])
            
            cursor.execute('''
                INSERT INTO accounts (username, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, username, email
            ''', (args['username'], args['email'], password_hash))
            
            new_account = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            return dict(new_account), 201
                
        except psycopg2.IntegrityError as e:
            error_msg = 'Ошибка уникальности: '
            if 'username' in str(e):
                error_msg += 'Имя пользователя уже существует'
            elif 'email' in str(e):
                error_msg += 'Email уже зарегистрирован'
            api.abort(409, error_msg)
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

@app.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, username, email, about_me FROM accounts')
        accounts = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row['table_name'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return render_template('view_db.html', accounts=accounts, tables=tables)
    
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/profile/<int:user_id>')
def user_profile(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, email, about_me 
            FROM accounts 
            WHERE id = %s
        ''', (user_id,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return render_template('404.html'), 404
            
        return render_template('profile.html', user=dict(user))
    except psycopg2.Error as e:
        return render_template('error.html', error=str(e)), 500

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
    def post(self, user_id):
        """Обновить имя пользователя"""
        data = api.payload
        new_username = data.get('new_username', '').strip()
        
        if not new_username:
            api.abort(400, 'Имя пользователя не может быть пустым')
        if len(new_username) < 3:
            api.abort(400, 'Имя пользователя должно содержать минимум 3 символа')
            
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM accounts WHERE id = %s', (user_id,))
            if not cursor.fetchone():
                api.abort(404, 'Пользователь не найден')
            
            cursor.execute('SELECT id FROM accounts WHERE username = %s AND id != %s', 
                         (new_username, user_id))
            if cursor.fetchone():
                api.abort(409, 'Имя пользователя уже занято')
            
            cursor.execute('''
                UPDATE accounts 
                SET username = %s
                WHERE id = %s
                RETURNING id, username, email, about_me
            ''', (new_username, user_id))
            
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            return dict(result) if result else api.abort(404, 'Пользователь не найден')
                
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

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
            conn = get_db()
            cursor = conn.cursor()
        
            cursor.execute('''
                UPDATE accounts 
                SET about_me = %s
                WHERE id = %s
                RETURNING id, username, email, about_me
            ''', (about_me, user_id))
        
            if cursor.rowcount == 0:
                api.abort(404, 'Пользователь не найден')
        
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
        
            return dict(result)
        
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

    @api.doc('get_user_info')
    @api.marshal_with(account_model)
    def get(self, user_id):
        """Получить информацию о пользователе"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, username, email, about_me 
                FROM accounts 
                WHERE id = %s
            ''', (user_id,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                api.abort(404, 'Пользователь не найден')
                
            return dict(user)
            
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

    @api.doc('delete_about_me')
    def delete(self, user_id):
        """Удалить информацию 'О себе'"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE accounts 
                SET about_me = '' 
                WHERE id = %s
            ''', (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return {'message': 'Информация удалена'}
        except psycopg2.Error as e:
            api.abort(500, 'Ошибка базы данных')

if __name__ == '__main__':
    init_db()
    app.run()
