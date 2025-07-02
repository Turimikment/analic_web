from flask import Blueprint, render_template, redirect, url_for
from app.extensions import app

bp = Blueprint('main', __name__)

@bp.route('/')
def welcome():
    return render_template('welcome.html')

@bp.route('/main')
def main_page():
    return render_template('index.html')

@bp.route('/pipeline')
def pipeline():
    return render_template('pipeline.html')

@bp.route('/redis-stats')
def redis_stats_page():
    return render_template('redis_stats.html')

@bp.route('/normalization-tutorial')
def normalization_tutorial():
    return render_template('normalization_tutorial.html')

@bp.route('/soap-interface')
def soap_interface():
    return render_template('soap.html')


@bp.route('/search')
def search_page():
    return render_template('search_holidays.html')