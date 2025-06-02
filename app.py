from flask import Flask, request, render_template, jsonify, redirect, url_for
from flasgger import Swagger
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dynamic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Конфигурация Swagger
app.config['SWAGGER'] = {
    'title': 'Dynamic API Generator',
    'uiversion': 3
}
swagger = Swagger(app)

# Хранилище для описаний динамических моделей
dynamic_models = {}

def create_dynamic_model(model_name, fields):
    """Создает динамическую модель SQLAlchemy на основе описания полей"""
    attrs = {
        '__tablename__': model_name.lower(),
        'id': db.Column(db.Integer, primary_key=True)
    }
    
    for field in fields:
        field_name = field['name']
        field_type = field['type'].lower()
        
        if field_type == 'string':
            attrs[field_name] = db.Column(db.String(100))
        elif field_type == 'integer':
            attrs[field_name] = db.Column(db.Integer)
        elif field_type == 'float':
            attrs[field_name] = db.Column(db.Float)
        elif field_type == 'boolean':
            attrs[field_name] = db.Column(db.Boolean)
        else:
            attrs[field_name] = db.Column(db.String(100))
    
    DynamicModel = type(model_name, (db.Model,), attrs)
    return DynamicModel

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        endpoint = request.form.get('endpoint').strip()
        fields_text = request.form.get('fields').strip()
        
        try:
            fields = []
            for line in fields_text.split('\n'):
                if line.strip():
                    name, type_ = line.split(':')
                    fields.append({'name': name.strip(), 'type': type_.strip()})
            
            # Создаем модель
            model_name = endpoint.capitalize()
            DynamicModel = create_dynamic_model(model_name, fields)
            
            # Регистрируем endpoint'ы
            register_crud_routes(DynamicModel, endpoint)
            
            # Сохраняем описание модели
            dynamic_models[endpoint] = {
                'model': model_name,
                'fields': fields
            }
            
            # Создаем таблицу в БД
            db.create_all()
            
            return redirect(url_for('show_endpoint', endpoint_name=endpoint))
        except Exception as e:
            return render_template('index.html', 
                                error=str(e),
                                endpoint_value=request.form.get('endpoint'),
                                fields_value=request.form.get('fields'))
    
    return render_template('index.html')

@app.route('/endpoint/<endpoint_name>')
def show_endpoint(endpoint_name):
    if endpoint_name not in dynamic_models:
        return redirect(url_for('index'))
    
    endpoint_info = dynamic_models[endpoint_name]
    example_data = {field['name']: f"example_{field['type']}" for field in endpoint_info['fields']}
    
    return render_template('endpoint.html',
                         endpoint_name=endpoint_name,
                         fields=endpoint_info['fields'],
                         example_data=example_data,
                         swagger_url="/apidocs")

def register_crud_routes(model, endpoint):
    """Регистрирует CRUD маршруты для модели"""
    
    @app.route(f'/{endpoint}', methods=['POST'])
    def create_item():
        """Создание новой записи"""
        data = request.get_json()
        item = model(**data)
        db.session.add(item)
        db.session.commit()
        return jsonify({'message': 'Item created', 'id': item.id}), 201
    
    @app.route(f'/{endpoint}/<int:id>', methods=['GET'])
    def read_item(id):
        """Получение записи по ID"""
        item = model.query.get_or_404(id)
        return jsonify({col.name: getattr(item, col.name) for col in model.__table__.columns})
    
    @app.route(f'/{endpoint}', methods=['GET'])
    def list_items():
        """Получение всех записей"""
        items = model.query.all()
        return jsonify([
            {col.name: getattr(item, col.name) for col in model.__table__.columns} 
            for item in items
        ])
    
    @app.route(f'/{endpoint}/<int:id>', methods=['PUT'])
    def update_item(id):
        """Обновление записи"""
        item = model.query.get_or_404(id)
        data = request.get_json()
        for key, value in data.items():
            setattr(item, key, value)
        db.session.commit()
        return jsonify({'message': 'Item updated'})
    
    @app.route(f'/{endpoint}/<int:id>', methods=['DELETE'])
    def delete_item(id):
        """Удаление записи"""
        item = model.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Item deleted'})

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
