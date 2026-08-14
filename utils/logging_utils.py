import json
import logging
import os
import time
import uuid

import requests
from flask import g, request, session


class JsonFormatter(logging.Formatter):
    """Formats log records as one-line JSON for stdout and Loki."""

    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
            'level': record.levelname.lower(),
            'logger': record.name,
            'message': record.getMessage(),
        }

        event = getattr(record, 'event_data', None)
        if isinstance(event, dict):
            payload.update(event)

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class LokiHandler(logging.Handler):
    """Simple fail-safe Loki handler suitable for Gunicorn workers."""

    def __init__(self, loki_url, service='analic-web', environment='production'):
        super().__init__()
        self.loki_url = loki_url.rstrip('/') + '/loki/api/v1/push'
        self.service = service
        self.environment = environment
        print(f'[LOKI] enabled: {self.loki_url}', flush=True)

    def emit(self, record):
        try:
            message = self.format(record)
            event = getattr(record, 'event_data', None)
            component = 'app'
            if isinstance(event, dict):
                component = event.get('component') or component

            payload = {
                'streams': [{
                    'stream': {
                        'service': self.service,
                        'environment': self.environment,
                        'component': component,
                        'level': record.levelname.lower(),
                    },
                    'values': [[str(time.time_ns()), message]],
                }]
            }

            # Keep Loki completely fail-safe for the application.  The short
            # timeout prevents an unavailable Loki from noticeably delaying a
            # normal request, while avoiding a background thread created before
            # Gunicorn forks its worker process.
            response = requests.post(self.loki_url, json=payload, timeout=0.5)
            print(f'[LOKI] push response: {response.status_code}', flush=True)
            if not response.ok:
                body = (response.text or '')[:500]
                print(
                    f'[LOKI] push failed: status={response.status_code} response={body}',
                    flush=True,
                )
        except requests.RequestException as exc:
            print(f'[LOKI] push error: {exc}', flush=True)
        except Exception as exc:
            print(f'[LOKI] unexpected error: {exc}', flush=True)


def _build_access_logger():
    logger = logging.getLogger('http.access')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Avoid duplicate handlers when create_app() is called more than once.
    if logger.handlers:
        return logger

    formatter = JsonFormatter()

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    loki_url = os.environ.get('LOKI_URL', '').strip()
    if loki_url:
        loki_handler = LokiHandler(
            loki_url=loki_url,
            service=os.environ.get('LOKI_SERVICE', 'analic-web'),
            environment=os.environ.get('APP_ENV', os.environ.get('FLASK_ENV', 'production')),
        )
        loki_handler.setFormatter(formatter)
        logger.addHandler(loki_handler)
    else:
        print('[LOKI] disabled: LOKI_URL is not configured', flush=True)

    return logger


def init_request_logging(app):
    """Registers request/response logging without changing route behaviour."""
    access_logger = _build_access_logger()

    @app.before_request
    def _start_request_log():
        g.request_started_at = time.perf_counter()
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())

    @app.after_request
    def _finish_request_log(response):
        started_at = getattr(g, 'request_started_at', None)
        duration_ms = None
        if started_at is not None:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

        event = {
            'event': 'http_request',
            'request_id': getattr(g, 'request_id', None),
            'method': request.method,
            'path': request.path,
            'route': request.url_rule.rule if request.url_rule else None,
            'endpoint': request.endpoint,
            'component': request.blueprint or 'app',
            'status': response.status_code,
            'duration_ms': duration_ms,
            'user_id': session.get('user_id'),
        }

        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        access_logger.log(level, 'HTTP request completed', extra={'event_data': event})

        if getattr(g, 'request_id', None):
            response.headers['X-Request-ID'] = g.request_id
        return response

    @app.teardown_request
    def _log_unhandled_exception(error):
        if error is None:
            return

        event = {
            'event': 'http_request_exception',
            'request_id': getattr(g, 'request_id', None),
            'method': request.method,
            'path': request.path,
            'endpoint': request.endpoint,
            'component': request.blueprint or 'app',
            'user_id': session.get('user_id'),
        }
        access_logger.error(
            'Unhandled request exception',
            exc_info=(type(error), error, error.__traceback__),
            extra={'event_data': event},
        )
