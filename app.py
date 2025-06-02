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
