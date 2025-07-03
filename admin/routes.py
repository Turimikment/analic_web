# app/admin/routes.py
from flask import Blueprint, render_template, request, make_response
from utils import db_utils
import io
import csv
import zipfile
from datetime import datetime
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/view-db')
def view_database():
    """Просмотр содержимого базы данных"""
    try:
        selected_table = request.args.get('table', 'accounts')
        data, columns, sql_query = db_utils.get_table_data(selected_table)
        
        return render_template(
            'view_db.html',
            selected_table=selected_table,
            data=data,
            sql_query=sql_query.strip()
        )

    except Exception as e:
        logger.error(f"Database view error: {e}")
        return render_template('error.html', error=str(e)), 500

@admin_bp.route('/export-db')
def export_database():
    """Выгрузка текущей таблицы в CSV"""
    table = request.args.get('table', 'accounts')
    try:
        data, columns, _ = db_utils.get_table_data(table)
        
        # Формируем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        
        for row in data:
            writer.writerow([db_utils.format_value(value) for value in row])
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={table}.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        return render_template('error.html', error=str(e)), 500

@admin_bp.route('/export-db-all')
def export_all_database():
    """Выгрузка всей БД в ZIP с CSV"""
    try:
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
                    writer.writerow([db_utils.format_value(value) for value in row])
                    
                zip_file.writestr(f"{table}.csv", csv_output.getvalue())
        
        buffer.seek(0)
        response = make_response(buffer.read())
        response.headers["Content-Disposition"] = "attachment; filename=database_export.zip"
        response.headers["Content-type"] = "application/zip"
        return response
        
    except Exception as e:
        logger.error(f"Full export error: {e}")
        return render_template('error.html', error=str(e)), 500