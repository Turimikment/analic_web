# app.py
from flask import Flask, session, render_template
from flask_session import Session
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from spyne.server.wsgi import WsgiApplication
from config import Config
from main.routes import main_bp
from api.routes import api_bp
from admin.routes import admin_bp
from kafka.routes import kafka_bp
from soap.soap_service import soap_app
from utils.db_utils import init_db
from flasgger import Swagger
import logging
import os

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Фабрика для создания экземпляра приложения Flask"""
    app = Flask(__name__)
    
    # Загрузка конфигурации
    app.config.from_object(Config)
    
    # Настройка сессий
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    Session(app)
    
    # Регистрация компонентов
    register_blueprints(app)
    
    # Инициализация Swagger
    swagger = Swagger(app, config=app.config['SWAGGER'])
    
    # SOAP интеграция
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
        '/soap': WsgiApplication(soap_app)
    })
    
    # Регистрация обработчиков ошибок
    register_error_handlers(app)
    
    # Инициализация БД - выполняется при запуске приложения
    with app.app_context():
        try:
            init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
    
    return app

def register_blueprints(app):
    """Регистрирует все блюпринты приложения"""
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(kafka_bp, url_prefix='/kafka')
    logger.info("Blueprints registered")

def register_error_handlers(app):
    """Регистрирует обработчики ошибок"""
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"Server error: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500
    
    logger.info("Error handlers registered")

if __name__ == '__main__':
    # Создание и запуск приложения
    app = create_app()
    
    # Настройки для продакшена
    if os.environ.get('FLASK_ENV') == 'production':
        from waitress import serve
        logger.info("Starting production server")
        serve(app, host='0.0.0.0', port=5000)
    else:
        logger.info("Starting development server")
        app.run(debug=True, host='0.0.0.0')