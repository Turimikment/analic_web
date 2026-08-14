import calendar
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, redirect, render_template, request, session, url_for

from . import db
from .openrouter import customer_answer, make_review
from .scenario import INTRO, REVIEW_PROMPT, SYSTEM_PROMPT

ai_agent_bp=Blueprint('ai_agent',__name__)
MONTH_NAMES=['','Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def _today():
    try: return datetime.now(ZoneInfo(os.environ.get('APP_TIMEZONE','Europe/Moscow'))).date()
    except Exception: return date.today()

def _require_login(): return bool(session.get('logged_in') and session.get('user_id'))

@ai_agent_bp.route('/')
def index():
    if not _require_login(): return redirect(url_for('main.index'))
    today=_today()
    try:
        year=int(request.args.get('year',today.year)); month=int(request.args.get('month',today.month))
        if month<1 or month>12 or year<today.year-1 or year>today.year+2: raise ValueError
    except ValueError: year,month=today.year,today.month
    first=date(year,month,1); last=date(year,month,calendar.monthrange(year,month)[1])
    booking_map={(x['booking_date'],x['slot_number']):x for x in db.get_bookings(first,last)}
    weeks=calendar.Calendar(firstweekday=0).monthdatescalendar(year,month)
    uid=session['user_id']; today_booking=db.get_booking_for_user_on_date(uid,today); next_booking=db.get_next_booking_for_user(uid,today)
    messages=db.get_messages(today_booking['id']) if today_booking else []
    review=db.get_review(today_booking['id']) if today_booking else None
    py,pm=(year-1,12) if month==1 else (year,month-1); ny,nm=(year+1,1) if month==12 else (year,month+1)
    return render_template('ai_agent.html',username=session.get('username','Заяц'),today=today,year=year,month=month,month_name=MONTH_NAMES[month],weeks=weeks,booking_map=booking_map,slots=range(1,db.SLOTS_PER_DAY+1),question_limit=db.QUESTION_LIMIT,today_booking=today_booking,next_booking=next_booking,prev_year=py,prev_month=pm,next_year=ny,next_month=nm,error=request.args.get('error'),success=request.args.get('success'),messages=messages,review=review,intro=INTRO)

@ai_agent_bp.route('/book',methods=['POST'])
def book():
    if not _require_login(): return redirect(url_for('main.index'))
    try:
        d=date.fromisoformat(request.form.get('booking_date','')); slot=int(request.form.get('slot_number',''))
        if d<_today(): raise ValueError('Нельзя записаться на прошедшую дату')
        db.book_slot(session['user_id'],d,slot)
        return redirect(url_for('ai_agent.index',year=d.year,month=d.month,success=f'Запись создана на {d.strftime("%d.%m.%Y")}'))
    except (ValueError,TypeError) as exc: return redirect(url_for('ai_agent.index',error=str(exc)))

@ai_agent_bp.route('/cancel/<int:booking_id>',methods=['POST'])
def cancel(booking_id):
    if not _require_login(): return redirect(url_for('main.index'))
    if db.cancel_booking(session['user_id'],booking_id): return redirect(url_for('ai_agent.index',success='Запись отменена'))
    return redirect(url_for('ai_agent.index',error='Не удалось отменить запись'))

@ai_agent_bp.route('/ask',methods=['POST'])
def ask():
    if not _require_login(): return redirect(url_for('main.index'))
    booking=db.get_booking_for_user_on_date(session['user_id'],_today())
    if not booking or booking['status']=='finished': return redirect(url_for('ai_agent.index',error='Интервью сегодня недоступно'))
    question=(request.form.get('question') or '').strip()
    if not question: return redirect(url_for('ai_agent.index',error='Введите вопрос'))
    if len(question)>1000: return redirect(url_for('ai_agent.index',error='Вопрос слишком длинный'))
    if booking['questions_used']>=db.QUESTION_LIMIT: return redirect(url_for('ai_agent.index',error='Лимит вопросов исчерпан'))
    try:
        history=db.get_messages(booking['id']); answer=customer_answer(SYSTEM_PROMPT,history,question)
        db.save_exchange(session['user_id'],booking['id'],question,answer)
        return redirect(url_for('ai_agent.index',tab='chat'))
    except Exception as exc:
        return redirect(url_for('ai_agent.index',tab='chat',error=f'AI временно недоступен: {str(exc)[:180]}'))

@ai_agent_bp.route('/finish',methods=['POST'])
def finish():
    if not _require_login(): return redirect(url_for('main.index'))
    booking=db.get_booking_for_user_on_date(session['user_id'],_today())
    if not booking or booking['status']=='finished': return redirect(url_for('ai_agent.index',error='Интервью недоступно'))
    try:
        history=db.get_messages(booking['id'])
        if not history: raise ValueError('Сначала задайте хотя бы один вопрос')
        review=make_review(REVIEW_PROMPT,SYSTEM_PROMPT,history)
        db.finish_interview(session['user_id'],booking['id'],review)
        return redirect(url_for('ai_agent.index',tab='chat',success='Интервью завершено'))
    except Exception as exc:
        return redirect(url_for('ai_agent.index',tab='chat',error=f'Не удалось завершить интервью: {str(exc)[:180]}'))
