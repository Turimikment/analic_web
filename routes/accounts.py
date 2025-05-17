from flask import Blueprint, jsonify, request
from database import get_db
from models.schemas import account_model, create_account_model
from utils.validators import validate_email
import psycopg2
from psycopg2 import errors

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

@accounts_bp.route('/', methods=['GET'])
def get_accounts():
    # ... (ваш код обработчика)

@accounts_bp.route('/', methods=['POST'])
def create_account():
    # ... (ваш код обработчика)

# ... остальные методы для accounts