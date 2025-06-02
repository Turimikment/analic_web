from flask import Flask, request, render_template, jsonify
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
            
            return render_template('index.html', 
                                 success=f"Endpoint /{endpoint} создан!",
                                 swagger_url="/apidocs")
        except Exception as e:
            return render_template('index.html', error=str(e))
    
    return render_template('index.html')

def register_crud_routes(model, endpoint):
    """Регистрирует CRUD маршруты для модели"""
    
    @app.route(f'/{endpoint}', methods=['POST'])
    def create_item():
        """Создание новой записи
        ---
        tags:
          - Dynamic API
        parameters:
          - in: body
            name: body
            schema:
              id: {endpoint}_create
              required:
                - {required_fields}
              properties:
                {fields_schema}
        responses:
          201:
            description: Запись создана
        """
        data = request.get_json()
        item = model(**data)
        db.session.add(item)
        db.session.commit()
        return jsonify({'message': 'Item created', 'id': item.id}), 201
    
    @app.route(f'/{endpoint}/<int:id>', methods=['GET'])
    def read_item(id):
        """Получение записи по ID
        ---
        tags:
          - Dynamic API
        parameters:
          - name: id
            in: path
            type: integer
            required: true
        responses:
          200:
            description: Запись найдена
          404:
            description: Запись не найдена
        """
        item = model.query.get_or_404(id)
        return jsonify({col.name: getattr(item, col.name) for col in model.__table__.columns})
    
    @app.route(f'/{endpoint}', methods=['GET'])
    def list_items():
        """Получение всех записей
        ---
        tags:
          - Dynamic API
        responses:
          200:
            description: Список записей
        """
        items = model.query.all()
        return jsonify([
            {col.name: getattr(item, col.name) for col in model.__table__.columns} 
            for item in items
        ])
    
    @app.route(f'/{endpoint}/<int:id>', methods=['PUT'])
    def update_item(id):
        """Обновление записи
        ---
        tags:
          - Dynamic API
        parameters:
          - name: id
            in: path
            type: integer
            required: true
          - in: body
            name: body
            schema:
              id: {endpoint}_update
              properties:
                {fields_schema}
        responses:
          200:
            description: Запись обновлена
          404:
            description: Запись не найдена
        """
        item = model.query.get_or_404(id)
        data = request.get_json()
        for key, value in data.items():
            setattr(item, key, value)
        db.session.commit()
        return jsonify({'message': 'Item updated'})
    
    @app.route(f'/{endpoint}/<int:id>', methods=['DELETE'])
    def delete_item(id):
        """Удаление записи
        ---
        tags:
          - Dynamic API
        parameters:
          - name: id
            in: path
            type: integer
            required: true
        responses:
          200:
            description: Запись удалена
          404:
            description: Запись не найдена
        """
        item = model.query.get_or_404(id)
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Item deleted'})

@app.before_first_request
def create_tables():
    """Создает таблицы при первом запросе"""
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
