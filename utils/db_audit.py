import functools

from utils import db_utils
from utils.logging_utils import log_db_change


_AUDIT_INSTALLED = False


def _wrap_result(function_name, audit_callback):
    original = getattr(db_utils, function_name)

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            audit_callback(result, args, kwargs)
        except Exception:
            # Audit must never affect database/business behaviour.
            pass
        return result

    setattr(db_utils, function_name, wrapped)


def _arg(args, kwargs, position, name, default=None):
    if name in kwargs:
        return kwargs[name]
    if len(args) > position:
        return args[position]
    return default


def init_db_audit():
    """Installs non-invasive audit wrappers around DB mutation functions."""
    global _AUDIT_INSTALLED
    if _AUDIT_INSTALLED:
        return

    _wrap_result(
        'create_account',
        lambda result, args, kwargs: result and log_db_change(
            entity='account',
            operation='create',
            entity_id=result.get('id'),
            fields=['username', 'email', 'password_hash', 'creation_method', 'about_me'],
            creation_method=result.get('creation_method'),
        ),
    )

    _wrap_result(
        'update_username',
        lambda result, args, kwargs: result and log_db_change(
            entity='account',
            operation='update',
            entity_id=_arg(args, kwargs, 0, 'user_id'),
            fields=['username'],
        ),
    )

    _wrap_result(
        'update_about_me',
        lambda result, args, kwargs: result and log_db_change(
            entity='account',
            operation='update',
            entity_id=_arg(args, kwargs, 0, 'user_id'),
            fields=['about_me'],
        ),
    )

    _wrap_result(
        'delete_about_me',
        lambda result, args, kwargs: result and log_db_change(
            entity='account',
            operation='update',
            entity_id=_arg(args, kwargs, 0, 'user_id'),
            fields=['about_me'],
            action='clear',
        ),
    )

    _wrap_result(
        'delete_account',
        lambda result, args, kwargs: result and log_db_change(
            entity='account',
            operation='delete',
            entity_id=_arg(args, kwargs, 0, 'user_id'),
        ),
    )

    _wrap_result(
        'create_holiday',
        lambda result, args, kwargs: result and log_db_change(
            entity='holiday',
            operation='create',
            entity_id=result.get('id'),
            fields=['start_time', 'location', 'title'],
        ),
    )

    _wrap_result(
        'add_user_to_holiday',
        lambda result, args, kwargs: result and log_db_change(
            entity='user_holiday',
            operation='create',
            entity_id=result.get('id'),
            fields=['user_id', 'holiday_id'],
            target_user_id=_arg(args, kwargs, 0, 'user_id'),
            holiday_id=_arg(args, kwargs, 1, 'holiday_id'),
        ),
    )

    _wrap_result(
        'delete_holiday',
        lambda result, args, kwargs: result and log_db_change(
            entity='holiday',
            operation='delete',
            entity_id=_arg(args, kwargs, 0, 'holiday_id'),
        ),
    )

    _AUDIT_INSTALLED = True
