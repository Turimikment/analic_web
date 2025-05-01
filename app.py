from flask import Flask, render_template, request
from flask_restx import Api, Resource, fields
from werkzeug.security import generate_password_hash
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
api = Api(app)

# Database configuration
def get_db_connection():
    return psycopg2.connect(os.getenv('postgresql://db_analitick_veb_user:qtUD994hJSlRfZ79F95fZMDajBKOuVuo@dpg-d09ln50gjchc7398l9bg-a.oregon-postgres.render.com/db_analitick_veb'))

# Models
account_model = api.model('Account', {
    'id': fields.Integer(readonly=True),
    'username': fields.String(required=True),
    'email': fields.String(required=True),
    'about_me': fields.String,
    'created_at': fields.DateTime
})

# Initialize database
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(100) NOT NULL,
            about_me TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# Routes
@api.route('/accounts')
class AccountsResource(Resource):
    @api.marshal_list_with(account_model)
    def get(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, about_me, created_at FROM accounts')
        accounts = cursor.fetchall()
        cursor.close()
        conn.close()
        return [
            {
                'id': acc[0],
                'username': acc[1],
                'email': acc[2],
                'about_me': acc[3],
                'created_at': acc[4].isoformat()
            } for acc in accounts
        ]

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
