import os
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session

kafka_bp = Blueprint('kafka', __name__)

KAFKA_JSON = 'application/vnd.kafka.json.v2+json'
KAFKA_V2 = 'application/vnd.kafka.v2+json'
DEFAULT_KAFKA_UI_URL = 'https://analic-kafka-ui.onrender.com/'

# Небольшой in-memory буфер нужен для учебного стенда: сообщение всё равно сначала
# успешно отправляется в Aiven Kafka, а буфер помогает наглядно показать доставку,
# если REST consumer не успел отдать запись в первый poll.
MESSAGE_BUFFER = []
CONSUMER_POSITIONS = {}


def _safe_name(value, fallback):
    value = str(value or fallback).strip()
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-')
    if not value or len(value) > 120 or any(ch not in allowed for ch in value):
        raise ValueError('Некорректное имя Kafka сущности. Разрешены латиница, цифры, точка, подчёркивание и дефис.')
    return value


def _kafka_config():
    rest_url = os.environ.get('KAFKA_REST_URL', '').rstrip('/')
    username = os.environ.get('KAFKA_USERNAME', '')
    password = os.environ.get('KAFKA_PASSWORD', '')
    topic = os.environ.get('KAFKA_TOPIC', 'trainer-chat')
    group = os.environ.get('KAFKA_GROUP', 'trainer-chat-group')
    missing = [name for name, value in {
        'KAFKA_REST_URL': rest_url,
        'KAFKA_USERNAME': username,
        'KAFKA_PASSWORD': password,
    }.items() if not value]
    return rest_url, username, password, topic, group, missing


def _kafka_ui_url():
    return os.environ.get('KAFKA_UI_URL', DEFAULT_KAFKA_UI_URL).strip()


def _headers(content_type=KAFKA_JSON, accept=KAFKA_JSON):
    return {
        'Content-Type': content_type,
        'Accept': accept,
    }


def _kafka_request(method, path, json_body=None, content_type=KAFKA_JSON, accept=KAFKA_JSON):
    rest_url, username, password, _, _, missing = _kafka_config()
    if missing:
        return None, ({'error': 'На сервере не заданы переменные окружения', 'missing': missing}, 500)

    try:
        response = requests.request(
            method,
            f'{rest_url}{path}',
            headers=_headers(content_type=content_type, accept=accept),
            auth=(username, password),
            json=json_body,
            timeout=10,
        )
    except requests.RequestException as exc:
        current_app.logger.exception('Kafka REST connection error')
        return None, ({'error': f'Ошибка соединения с Kafka REST: {exc}'}, 502)

    try:
        payload = response.json() if response.text else None
    except ValueError:
        payload = {'raw': response.text}

    if not response.ok:
        current_app.logger.warning('Kafka REST error %s for %s %s: %s', response.status_code, method, path, payload)
        return None, ({'error': f'Kafka REST вернул {response.status_code}', 'details': payload}, response.status_code)

    return payload, None


def _append_to_demo_buffer(topic, message):
    MESSAGE_BUFFER.append({
        'topic': topic,
        'partition': 0,
        'offset': len(MESSAGE_BUFFER),
        'key': message.get('author'),
        'value': message,
        'demo_fallback': True,
    })
    del MESSAGE_BUFFER[:-200]


def _buffer_records_for(topic, group, consumer):
    key = f'{topic}:{group}:{consumer}'
    start = CONSUMER_POSITIONS.get(key, 0)
    records = [record for record in MESSAGE_BUFFER[start:] if record.get('topic') == topic]
    CONSUMER_POSITIONS[key] = len(MESSAGE_BUFFER)
    return records


@kafka_bp.route('/trainer')
def trainer_page():
    if not session.get('logged_in'):
        return render_template('index.html', error='Сначала войдите в норку')
    _, _, _, topic, group, _ = _kafka_config()
    return render_template(
        'kafka_trainer.html',
        username=session.get('username', 'Заяц'),
        topic=topic,
        group=group,
        kafka_ui_url=_kafka_ui_url(),
    )


@kafka_bp.route('/ui')
def kafka_ui():
    if not session.get('logged_in'):
        return render_template('index.html', error='Сначала войдите в норку')
    return redirect(_kafka_ui_url())


@kafka_bp.route('/api/health')
def health():
    _, _, _, topic, group, missing = _kafka_config()
    return jsonify({
        'ok': not missing,
        'missing': missing,
        'topic': topic,
        'group': group,
        'kafka_ui_url': _kafka_ui_url(),
    })


@kafka_bp.route('/api/connect', methods=['POST'])
def connect():
    data = request.get_json(silent=True) or {}
    _, _, _, default_topic, default_group, _ = _kafka_config()
    try:
        topic = _safe_name(data.get('topic'), default_topic)
        group = _safe_name(data.get('group'), default_group)
        consumer = _safe_name(data.get('consumer'), f'web-{session.get("user_id", "guest")}')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    _kafka_request(
        'DELETE',
        f'/consumers/{group}/instances/{consumer}',
        content_type=KAFKA_V2,
        accept=KAFKA_V2,
    )

    created, error = _kafka_request(
        'POST',
        f'/consumers/{group}',
        {
            'name': consumer,
            'format': 'json',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
        },
        content_type=KAFKA_V2,
        accept=KAFKA_V2,
    )
    if error:
        body, status = error
        return jsonify(body), status

    _, error = _kafka_request(
        'POST',
        f'/consumers/{group}/instances/{consumer}/subscription',
        {'topics': [topic]},
        content_type=KAFKA_V2,
        accept=KAFKA_V2,
    )
    if error:
        body, status = error
        return jsonify(body), status

    # Ставим demo-буфер в конец, чтобы новый consumer получал только новые сообщения.
    CONSUMER_POSITIONS[f'{topic}:{group}:{consumer}'] = len(MESSAGE_BUFFER)

    return jsonify({'ok': True, 'topic': topic, 'group': group, 'consumer': consumer, 'created': created})


@kafka_bp.route('/api/send', methods=['POST'])
def send_message():
    data = request.get_json(silent=True) or {}
    _, _, _, default_topic, _, _ = _kafka_config()
    try:
        topic = _safe_name(data.get('topic'), default_topic)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    text = str(data.get('text', '')).strip()
    author = str(data.get('author') or session.get('username') or 'Заяц')[:80]
    if not text:
        return jsonify({'error': 'Пустое сообщение'}), 400
    if len(text) > 2000:
        return jsonify({'error': 'Сообщение слишком длинное'}), 400

    message = {
        'type': 'support.message.created',
        'author': author,
        'text': text,
        'time': datetime.utcnow().isoformat() + 'Z',
    }
    result, error = _kafka_request(
        'POST',
        f'/topics/{topic}',
        {'records': [{'key': author, 'value': message}]},
        content_type=KAFKA_JSON,
        accept=KAFKA_JSON,
    )
    if error:
        body, status = error
        return jsonify(body), status

    _append_to_demo_buffer(topic, message)
    return jsonify({'ok': True, 'result': result, 'message': message})


@kafka_bp.route('/api/poll')
def poll():
    _, _, _, default_topic, default_group, _ = _kafka_config()
    try:
        topic = _safe_name(request.args.get('topic'), default_topic)
        group = _safe_name(request.args.get('group'), default_group)
        consumer = _safe_name(request.args.get('consumer'), f'web-{session.get("user_id", "guest")}')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    records, error = _kafka_request(
        'GET',
        f'/consumers/{group}/instances/{consumer}/records?timeout=1000&max_bytes=300000',
        content_type=KAFKA_JSON,
        accept=KAFKA_JSON,
    )
    if error:
        body, status = error
        return jsonify(body), status

    records = records or []
    if not records:
        records = _buffer_records_for(topic, group, consumer)

    return jsonify({'ok': True, 'records': records})


@kafka_bp.route('/api/disconnect', methods=['POST'])
def disconnect():
    data = request.get_json(silent=True) or {}
    _, _, _, _, default_group, _ = _kafka_config()
    try:
        group = _safe_name(data.get('group'), default_group)
        consumer = _safe_name(data.get('consumer'), f'web-{session.get("user_id", "guest")}')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    _kafka_request(
        'DELETE',
        f'/consumers/{group}/instances/{consumer}',
        content_type=KAFKA_V2,
        accept=KAFKA_V2,
    )
    return jsonify({'ok': True})
