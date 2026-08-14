import calendar
import os
from datetime import date,datetime
from zoneinfo import ZoneInfo
from flask import Blueprint,make_response,redirect,render_template,request,session,url_for
from . import db
from .openrouter import customer_answer,make_review
from .scenario import AGENTS,BUSINESS_PROMPT,DEVELOPER_PROMPT,REVIEW_PROMPT

ai_agent_bp=Blueprint('ai_agent',__name__)
MONTH_NAMES=['','Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
PROMPTS={'business':BUSINESS_PROMPT,'developer':DEVELOPER_PROMPT}

def _today():
    try:return datetime.now(ZoneInfo(os.environ.get('APP_TIMEZONE','Europe/Moscow'))).date()
    except Exception:return date.today()
def _require_login():return bool(session.get('logged_in') and session.get('user_id'))

def _review_context(booking_id):
    all_messages=db.get_messages(booking_id)
    lines=[]
    for m in all_messages:
        who=AGENTS.get(m['agent'],{}).get('name',m['agent'])
        lines.append(f"{('СТУДЕНТ' if m['role']=='user' else who)}: {m['content']}")
    spec=db.get_latest_spec(booking_id)
    return '\n'.join(lines),spec

@ai_agent_bp.route('/')
def index():
    if not _require_login():return redirect(url_for('main.index'))
    today=_today()
    try:
        year=int(request.args.get('year',today.year));month=int(request.args.get('month',today.month))
        if month<1 or month>12 or year<today.year-1 or year>today.year+2:raise ValueError
    except ValueError:year,month=today.year,today.month
    first=date(year,month,1);last=date(year,month,calendar.monthrange(year,month)[1])
    booking_map={(x['booking_date'],x['slot_number']):x for x in db.get_bookings(first,last)}
    weeks=calendar.Calendar(firstweekday=0).monthdatescalendar(year,month)
    uid=session['user_id'];booking=db.get_booking_for_user_on_date(uid,today);next_booking=db.get_next_booking_for_user(uid,today)
    active_agent=request.args.get('agent','business')
    if active_agent not in AGENTS:active_agent='business'
    chats={a:db.get_messages(booking['id'],a) if booking else [] for a in AGENTS}
    spec=db.get_latest_spec(booking['id']) if booking else {'mermaid':'','api_spec':'','business_rules':''}
    review=db.get_review(booking['id']) if booking else None
    py,pm=(year-1,12) if month==1 else(year,month-1);ny,nm=(year+1,1) if month==12 else(year,month+1)
    html=render_template('ai_agent.html',username=session.get('username','Заяц'),today=today,year=year,month=month,month_name=MONTH_NAMES[month],weeks=weeks,booking_map=booking_map,slots=range(1,db.SLOTS_PER_DAY+1),question_limit=db.QUESTION_LIMIT,today_booking=booking,next_booking=next_booking,prev_year=py,prev_month=pm,next_year=ny,next_month=nm,error=request.args.get('error'),success=request.args.get('success'),agents=AGENTS,active_agent=active_agent,chats=chats,spec=spec,review=review)
    response=make_response(html);response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0';response.headers['Pragma']='no-cache';response.headers['Expires']='0';return response

@ai_agent_bp.route('/book',methods=['POST'])
def book():
    if not _require_login():return redirect(url_for('main.index'))
    try:
        d=date.fromisoformat(request.form.get('booking_date',''));slot=int(request.form.get('slot_number',''))
        if d<_today():raise ValueError('Нельзя записаться на прошедшую дату')
        db.book_slot(session['user_id'],d,slot);return redirect(url_for('ai_agent.index',year=d.year,month=d.month,success=f'Запись создана на {d.strftime("%d.%m.%Y")}'))
    except(ValueError,TypeError)as exc:return redirect(url_for('ai_agent.index',error=str(exc)))

@ai_agent_bp.route('/cancel/<int:booking_id>',methods=['POST'])
def cancel(booking_id):
    if not _require_login():return redirect(url_for('main.index'))
    if db.cancel_booking(session['user_id'],booking_id):return redirect(url_for('ai_agent.index',success='Запись отменена'))
    return redirect(url_for('ai_agent.index',error='Не удалось отменить запись'))

@ai_agent_bp.route('/ask',methods=['POST'])
def ask():
    if not _require_login():return redirect(url_for('main.index'))
    uid=session['user_id'];booking=db.get_booking_for_user_on_date(uid,_today());agent=request.form.get('agent','business')
    if agent not in AGENTS:return redirect(url_for('ai_agent.index',tab='chat',error='Неизвестный собеседник'))
    if not booking or booking['status']=='finished':return redirect(url_for('ai_agent.index',error='Симуляция сегодня недоступна'))
    question=(request.form.get('question')or'').strip()
    if not question:return redirect(url_for('ai_agent.index',tab='chat',agent=agent,error='Введите сообщение'))
    if len(question)>1500:return redirect(url_for('ai_agent.index',tab='chat',agent=agent,error='Сообщение слишком длинное'))
    if booking['questions_used']>=db.QUESTION_LIMIT:return redirect(url_for('ai_agent.index',tab='chat',agent=agent,error='Лимит сообщений исчерпан'))
    reserved=False
    try:
        db.begin_question(uid,booking['id']);reserved=True
        history=[{'role':m['role'],'content':m['content']} for m in db.get_messages(booking['id'],agent)]
        prompt=PROMPTS[agent]
        if agent=='developer':
            spec=db.get_latest_spec(booking['id'])
            prompt+=f"\n\nТекущая переданная спецификация аналитика:\nMERMAID:\n{spec['mermaid'] or '(не передана)'}\n\nAPI:\n{spec['api_spec'] or '(не передано)'}\n\nБизнес-правила:\n{spec['business_rules'] or '(не переданы)'}"
        answer=customer_answer(prompt,history,question)
        db.save_exchange(uid,booking['id'],agent,question,answer);reserved=False
        return redirect(url_for('ai_agent.index',tab='chat',agent=agent))
    except Exception as exc:
        if reserved:
            try:db.release_question(uid,booking['id'])
            except Exception:pass
        return redirect(url_for('ai_agent.index',tab='chat',agent=agent,error=f'AI временно недоступен: {str(exc)[:180]}'))

@ai_agent_bp.route('/spec',methods=['POST'])
def save_spec():
    if not _require_login():return redirect(url_for('main.index'))
    booking=db.get_booking_for_user_on_date(session['user_id'],_today())
    if not booking:return redirect(url_for('ai_agent.index',error='Симуляция сегодня недоступна'))
    try:
        mermaid=(request.form.get('mermaid')or'').strip();api_spec=(request.form.get('api_spec')or'').strip();rules=(request.form.get('business_rules')or'').strip()
        if len(mermaid)+len(api_spec)+len(rules)>15000:raise ValueError('Спецификация слишком большая')
        db.save_spec(session['user_id'],booking['id'],mermaid,api_spec,rules)
        return redirect(url_for('ai_agent.index',tab='chat',agent='developer',success='Спецификация передана Максиму'))
    except Exception as exc:return redirect(url_for('ai_agent.index',tab='chat',agent='developer',error=str(exc)))

@ai_agent_bp.route('/finish',methods=['POST'])
def finish():
    if not _require_login():return redirect(url_for('main.index'))
    booking=db.get_booking_for_user_on_date(session['user_id'],_today())
    if not booking or booking['status']=='finished':return redirect(url_for('ai_agent.index',error='Симуляция недоступна'))
    try:
        transcript,spec=_review_context(booking['id'])
        if not transcript:raise ValueError('Сначала пообщайтесь хотя бы с одним стейкхолдером')
        context=f"Диалоги:\n{transcript}\n\nПоследняя спецификация:\nMERMAID:\n{spec['mermaid'] or '(нет)'}\n\nAPI:\n{spec['api_spec'] or '(нет)'}\n\nБизнес-правила:\n{spec['business_rules'] or '(нет)'}\n\nЭталон бизнеса:\n{BUSINESS_PROMPT}\n\nТехнический эталон:\n{DEVELOPER_PROMPT}"
        review=make_review(REVIEW_PROMPT,'Полная симуляция', [{'role':'user','content':context}])
        db.finish_interview(session['user_id'],booking['id'],review)
        return redirect(url_for('ai_agent.index',tab='chat',success='Симуляция завершена'))
    except Exception as exc:return redirect(url_for('ai_agent.index',tab='chat',error=f'Не удалось завершить: {str(exc)[:180]}'))
