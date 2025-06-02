from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
import os
import uuid
import json

app = Flask(__name__)
base_dir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(base_dir, 'instance')
os.makedirs(db_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(db_path, "dynamic_api.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Swagger configuration
SWAGGER_URL = '/swagger'
API_URL = '/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Dynamic API Generator"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/swagger.json')
def swagger():
    endpoints = DynamicEndpoint.query.all()
    swagger_doc = {
        "openapi": "3.0.0",
        "info": {
            "title": "Dynamic API",
            "version": "1.0.0",
            "description": "API dynamically generated from user input"
        },
        "paths": {}
    }
    
    for endpoint in endpoints:
        path = f"/api/{endpoint.endpoint_name}"
        swagger_doc["paths"][path] = {
            "get": {
                "summary": f"Get records from {endpoint.endpoint_name}",
                "responses": {
                    "200": {
                        "description": "A list of records",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": json.loads(endpoint.fields_description)
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "summary": f"Add a record to {endpoint.endpoint_name}",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": json.loads(endpoint.fields_description)
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Record created successfully"
                    }
                }
            }
        }
    
    return jsonify(swagger_doc)
@app.context_processor
def inject_swagger_url():
    return dict(swagger_url=SWAGGER_URL)
    
class DynamicEndpoint(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    endpoint_name = db.Column(db.String(80), unique=True, nullable=False)
    fields_description = db.Column(db.Text, nullable=False)
    table_name = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<DynamicEndpoint {self.endpoint_name}>'

def init_db():
    """Инициализация базы данных"""
    with app.app_context():
        db.create_all()
        print(f"Database initialized at: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Проверка существующих таблиц
        inspector = db.inspect(db.engine)
        print("Existing tables:", inspector.get_table_names())

def create_dynamic_model(table_name, fields):
    """Создает динамическую модель SQLAlchemy"""
    attributes = {
        '__tablename__': table_name,
        'id': db.Column(db.Integer, primary_key=True),
        '__table_args__': {'extend_existing': True}  # Разрешает использование существующих таблиц
    }
    
    for field in fields:
        field_name = field['name']
        field_type = field['type'].lower()
        
        if field_type == 'string':
            attributes[field_name] = db.Column(db.String(100))
        elif field_type == 'integer':
            attributes[field_name] = db.Column(db.Integer)
        elif field_type == 'float':
            attributes[field_name] = db.Column(db.Float)
        elif field_type == 'boolean':
            attributes[field_name] = db.Column(db.Boolean)
        else:
            attributes[field_name] = db.Column(db.String(100))
    
    return type(table_name, (db.Model,), attributes)

# Инициализация базы данных
init_db()

# Универсальный обработчик для всех динамических эндпоинтов
# Замените обработку POST-запроса в функции index() на этот код
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        endpoint_name = request.form.get('endpoint_name')
        fields_description = request.form.get('fields_description')
        
        try:
            # Парсим JSON как объект (словарь)
            fields_dict = json.loads(fields_description)
            if not isinstance(fields_dict, dict):
                raise ValueError("Fields description should be a JSON object")
            
            # Преобразуем словарь в список полей для совместимости
            fields = [{"name": name, "type": typ} for name, typ in fields_dict.items()]
            
            # Генерируем уникальное имя таблицы
            table_name = f"table_{str(uuid.uuid4()).replace('-', '_')}"
            
            # Создаем динамическую модель
            DynamicModel = create_dynamic_model(table_name, fields)
            
            # Создаем таблицу в базе данных
            with app.app_context():
                DynamicModel.__table__.create(db.engine)
            
            # Сохраняем информацию о endpoint'е
            new_endpoint = DynamicEndpoint(
                id=str(uuid.uuid4()),
                endpoint_name=endpoint_name,
                fields_description=json.dumps(fields_dict),  # Сохраняем как объект
                table_name=table_name
            )
            db.session.add(new_endpoint)
            db.session.commit()
            
            return redirect(url_for('index'))
        except json.JSONDecodeError:
            error = "Invalid JSON format for fields description"
        except ValueError as e:
            error = str(e)
        except Exception as e:
            error = f"An error occurred: {str(e)}"
            db.session.rollback()
            import traceback
            traceback.print_exc()
        
        return render_template('index.html', error=error)
    
    endpoints = DynamicEndpoint.query.all()
    return render_template('index.html', endpoints=endpoints)        
        return render_template('index.html', error=error)
    
    endpoints = DynamicEndpoint.query.all()
    return render_template('index.html', endpoints=endpoints)

@app.route('/delete/<endpoint_id>', methods=['POST'])
def delete_endpoint(endpoint_id):
    endpoint = DynamicEndpoint.query.get_or_404(endpoint_id)
    
    try:
        # Удаляем таблицу из базы данных
        db.engine.execute(f"DROP TABLE IF EXISTS {endpoint.table_name}")
        print(f"Deleted table: {endpoint.table_name}")
    except Exception as e:
        print(f"Error deleting table: {str(e)}")
    
    # Удаляем запись о endpoint'е
    db.session.delete(endpoint)
    db.session.commit()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
