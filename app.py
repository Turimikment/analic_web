from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger
from flasgger.utils import swag_from

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db/database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SWAGGER'] = {
    'title': 'Database Integration API',
    'uiversion': 3,
    'description': 'API for database integration with three fields'
}

db = SQLAlchemy(app)
swagger = Swagger(app)

# Модель для базы данных
class DataItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    field1 = db.Column(db.String(100), nullable=False)
    field2 = db.Column(db.Integer, nullable=True)
    field3 = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'field1': self.field1,
            'field2': self.field2,
            'field3': self.field3
        }

# Создаем таблицы при первом запуске
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    """Главная страница с описанием интеграции"""
    integration_description = """
    ## Интеграция с базой данных через API

    Это API предоставляет следующие эндпоинты для работы с базой данных:

    1. GET /api/data - Получить все записи
    2. GET /api/data/<id> - Получить конкретную запись
    3. POST /api/data - Создать новую запись
    4. PATCH /api/data/<id> - Обновить запись
    5. DELETE /api/data/<id> - Удалить запись

    Каждая запись содержит три поля:
    - field1: строка (обязательное)
    - field2: целое число (опциональное)
    - field3: число с плавающей точкой (опциональное)
    """
    return render_template('index.html', description=integration_description)

@app.route('/api/data', methods=['GET'])
@swag_from({
    'tags': ['Data'],
    'responses': {
        200: {
            'description': 'Список всех записей',
            'examples': {
                'application/json': [
                    {
                        'id': 1,
                        'field1': 'Пример строки',
                        'field2': 42,
                        'field3': 3.14
                    }
                ]
            }
        }
    }
})
def get_all_data():
    """Получить все записи из базы данных"""
    items = DataItem.query.all()
    return jsonify([item.to_dict() for item in items])

@app.route('/api/data/<int:item_id>', methods=['GET'])
@swag_from({
    'tags': ['Data'],
    'parameters': [
        {
            'name': 'item_id',
            'in': 'path',
            'type': 'integer',
            'required': 'true',
            'description': 'ID записи'
        }
    ],
    'responses': {
        200: {
            'description': 'Запись найдена',
            'examples': {
                'application/json': {
                    'id': 1,
                    'field1': 'Пример строки',
                    'field2': 42,
                    'field3': 3.14
                }
            }
        },
        404: {
            'description': 'Запись не найдена'
        }
    }
})
def get_data(item_id):
    """Получить конкретную запись по ID"""
    item = DataItem.query.get_or_404(item_id)
    return jsonify(item.to_dict())

@app.route('/api/data', methods=['POST'])
@swag_from({
    'tags': ['Data'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'field1': {
                        'type': 'string',
                        'description': 'Обязательное строковое поле'
                    },
                    'field2': {
                        'type': 'integer',
                        'description': 'Опциональное целое число'
                    },
                    'field3': {
                        'type': 'number',
                        'description': 'Опциональное число с плавающей точкой'
                    }
                },
                'required': ['field1']
            }
        }
    ],
    'responses': {
        201: {
            'description': 'Запись создана',
            'examples': {
                'application/json': {
                    'id': 1,
                    'field1': 'Новая строка',
                    'field2': 100,
                    'field3': 1.23
                }
            }
        },
        400: {
            'description': 'Неверные данные'
        }
    }
})
def create_data():
    """Создать новую запись"""
    data = request.get_json()
    
    if not data or 'field1' not in data:
        return jsonify({'error': 'field1 is required'}), 400
    
    new_item = DataItem(
        field1=data['field1'],
        field2=data.get('field2'),
        field3=data.get('field3')
    )
    
    db.session.add(new_item)
    db.session.commit()
    
    return jsonify(new_item.to_dict()), 201

@app.route('/api/data/<int:item_id>', methods=['PATCH'])
@swag_from({
    'tags': ['Data'],
    'parameters': [
        {
            'name': 'item_id',
            'in': 'path',
            'type': 'integer',
            'required': 'true',
            'description': 'ID записи для обновления'
        },
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'field1': {
                        'type': 'string',
                        'description': 'Строковое поле'
                    },
                    'field2': {
                        'type': 'integer',
                        'description': 'Целое число'
                    },
                    'field3': {
                        'type': 'number',
                        'description': 'Число с плавающей точкой'
                    }
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Запись обновлена',
            'examples': {
                'application/json': {
                    'id': 1,
                    'field1': 'Обновленная строка',
                    'field2': 99,
                    'field3': 2.71
                }
            }
        },
        404: {
            'description': 'Запись не найдена'
        }
    }
})
def update_data(item_id):
    """Обновить существующую запись"""
    item = DataItem.query.get_or_404(item_id)
    data = request.get_json()
    
    if 'field1' in data:
        item.field1 = data['field1']
    if 'field2' in data:
        item.field2 = data['field2']
    if 'field3' in data:
        item.field3 = data['field3']
    
    db.session.commit()
    return jsonify(item.to_dict())

@app.route('/api/data/<int:item_id>', methods=['DELETE'])
@swag_from({
    'tags': ['Data'],
    'parameters': [
        {
            'name': 'item_id',
            'in': 'path',
            'type': 'integer',
            'required': 'true',
            'description': 'ID записи для удаления'
        }
    ],
    'responses': {
        204: {
            'description': 'Запись удалена'
        },
        404: {
            'description': 'Запись не найдена'
        }
    }
})
def delete_data(item_id):
    """Удалить запись"""
    item = DataItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
