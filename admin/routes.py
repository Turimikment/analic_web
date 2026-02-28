# app/admin/routes.py
from flask import Blueprint, render_template, request, make_response
from utils import db_utils
import io
import csv
import zipfile
import logging
from datetime import datetime


# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        selected_table = request.args.get('table', 'accounts')
        logger.info(f"Requested table: {selected_table}")
        
        data, columns, sql_query = db_utils.get_table_data(selected_table)
        logger.info(f"Retrieved {len(data)} rows from table '{selected_table}'")
        
        # Преобразуем данные в список словарей для удобства работы в шаблоне
        formatted_data = []
        for row in data:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                
                # Форматируем значения даты/времени
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                
                row_dict[col] = value
            formatted_data.append(row_dict)
        
        return render_template(
            'view_db.html',
            selected_table=selected_table,
            data=formatted_data,
            columns=columns,
            sql_query=sql_query.strip()
        )

    except Exception as e:
        logger.exception(f"Database view error: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500

@admin_bp.route('/export-db')
def export_database():
    """Выгрузка текущей таблицы в CSV"""
    table = request.args.get('table', 'accounts')
    try:
        logger.info(f"Exporting table '{table}' to CSV")
        data, columns, _ = db_utils.get_table_data(table)
        
        # Формируем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        
        for row in data:
            formatted_row = []
            for value in row:
                # Форматируем значения
                if isinstance(value, datetime):
                    formatted_row.append(value.strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    formatted_row.append(str(value) if value is not None else '')
            writer.writerow(formatted_row)
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={table}.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
        
    except Exception as e:
        logger.exception(f"Export error: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500

@admin_bp.route('/export-db-all')
def export_all_database():
    """Выгрузка всей БД в ZIP с CSV"""
    try:
        logger.info("Exporting entire database to ZIP")
        buffer = io.BytesIO()
        tables = ['accounts', 'holidays', 'user_holidays']
        
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for table in tables:
                data, columns, _ = db_utils.get_table_data(table)
                
                # Формируем CSV для таблицы
                csv_output = io.StringIO()
                writer = csv.writer(csv_output, delimiter=';')
                writer.writerow(columns)
                
                for row in data:
                    formatted_row = []
                    for value in row:
                        # Форматируем значения
                        if isinstance(value, datetime):
                            formatted_row.append(value.strftime('%Y-%m-%d %H:%M:%S'))
                        else:
                            formatted_row.append(str(value) if value is not None else '')
                    writer.writerow(formatted_row)
                    
                zip_file.writestr(f"{table}.csv", csv_output.getvalue())
                logger.info(f"Added table '{table}' to ZIP archive")
        
        buffer.seek(0)
        response = make_response(buffer.read())
        response.headers["Content-Disposition"] = "attachment; filename=database_export.zip"
        response.headers["Content-type"] = "application/zip"
        return response
        
    except Exception as e:
        logger.exception(f"Full export error: {str(e)}")
        return render_template('errors/500.html', error=str(e)), 500