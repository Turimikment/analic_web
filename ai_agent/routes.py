import calendar
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, redirect, render_template, request, session, url_for

from . import db


ai_agent_bp = Blueprint('ai_agent', __name__)


def _today():
    tz_name = os.environ.get('APP_TIMEZONE', 'Europe/Moscow')
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        return date.today()


def _require_login():
    return bool(session.get('logged_in') and session.get('user_id'))


@ai_agent_bp.route('/')
def index():
    if not _require_login():
        return redirect(url_for('main.index'))

    today = _today()
    try:
        year = int(request.args.get('year', today.year))
        month = int(request.args.get('month', today.month))
        if month < 1 or month > 12 or year < today.year - 1 or year > today.year + 2:
            raise ValueError
    except ValueError:
        year, month = today.year, today.month

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    bookings = db.get_bookings(first_day, last_day)
    booking_map = {(item['booking_date'], item['slot_number']): item for item in bookings}

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    user_id = session['user_id']
    today_booking = db.get_booking_for_user_on_date(user_id, today)
    next_booking = db.get_next_booking_for_user(user_id, today)

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    return render_template(
        'ai_agent.html',
        username=session.get('username', 'Заяц'),
        today=today,
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        weeks=weeks,
        booking_map=booking_map,
        slots=range(1, db.SLOTS_PER_DAY + 1),
        question_limit=db.QUESTION_LIMIT,
        today_booking=today_booking,
        next_booking=next_booking,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        error=request.args.get('error'),
        success=request.args.get('success'),
    )


@ai_agent_bp.route('/book', methods=['POST'])
def book():
    if not _require_login():
        return redirect(url_for('main.index'))

    try:
        booking_date = date.fromisoformat(request.form.get('booking_date', ''))
        slot_number = int(request.form.get('slot_number', ''))
        if booking_date < _today():
            raise ValueError('Нельзя записаться на прошедшую дату')
        db.book_slot(session['user_id'], booking_date, slot_number)
        return redirect(url_for(
            'ai_agent.index',
            year=booking_date.year,
            month=booking_date.month,
            success=f'Запись создана на {booking_date.strftime("%d.%m.%Y")}',
        ))
    except (ValueError, TypeError) as exc:
        return redirect(url_for('ai_agent.index', error=str(exc)))


@ai_agent_bp.route('/cancel/<int:booking_id>', methods=['POST'])
def cancel(booking_id):
    if not _require_login():
        return redirect(url_for('main.index'))

    if db.cancel_booking(session['user_id'], booking_id):
        return redirect(url_for('ai_agent.index', success='Запись отменена'))
    return redirect(url_for('ai_agent.index', error='Не удалось отменить запись'))
