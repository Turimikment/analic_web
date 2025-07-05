import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey123!')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    SWAGGER = {
        "headers": [],
        "specs": [{"endpoint": "apispec", "route": "/apispec.json"}],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
    }