from flasgger import Swagger
from werkzeug.middleware.dispatcher import DispatcherMiddleware

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "definitions": {
        "Account": account_model,
        "CreateAccount": create_account_model,
        "UpdateUsername": update_username_model,
        "AboutMe": about_me_model,
    "swagger_ui_parameters": {
        "dom_id": "#swagger-ui",
        "plugins": [
            {"src": "/static/swagger-custom.js", "name": "CustomButtonPlugin"}
        ]
    },
    "static_url_path": "/static"
    }
}

def configure_app(app):
    app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'supersecretkey')
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )
    
    # Swagger configuration
    Swagger(app, config=swagger_config)

swagger_template = {
    # ... (ваша конфигурация Swagger из app.py)
}

