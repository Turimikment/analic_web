from datetime import date

from psycopg2 import errors

from utils.db_utils import get_db_connection


SLOTS_PER_DAY = 3
QUESTION_LIMIT = 15


def init_ai_agent_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_interview_bookings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    booking_date DATE NOT NULL,
                    slot_number SMALLINT NOT NULL CHECK (slot_number BETWEEN 1 AND 3),
                    questions_used SMALLINT NOT NULL DEFAULT 0 CHECK (questions_used >= 0 AND questions_used <= 15),
                    status VARCHAR(20) NOT NULL DEFAULT 'booked',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (booking_date, slot_number), UNIQUE (user_id, booking_date)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_interview_messages (
                    id SERIAL PRIMARY KEY,
                    booking_id INTEGER NOT NULL REFERENCES ai_interview_bookings(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','review')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_bookings_date ON ai_interview_bookings (booking_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_bookings_user ON ai_interview_bookings (user_id, booking_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_messages_booking ON ai_interview_messages (booking_id, id)')
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def _booking(row):
    if not row: return None
    return {'id':row[0],'user_id':row[1],'booking_date':row[2],'slot_number':row[3],'questions_used':row[4],'status':row[5]}


def get_bookings(start_date, end_date):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''SELECT b.id,b.user_id,a.username,b.booking_date,b.slot_number,b.questions_used,b.status
                         FROM ai_interview_bookings b JOIN accounts a ON a.id=b.user_id
                         WHERE b.booking_date BETWEEN %s AND %s AND b.status IN ('booked','started','finished')
                         ORDER BY b.booking_date,b.slot_number''',(start_date,end_date))
            return [{'id':r[0],'user_id':r[1],'username':r[2],'booking_date':r[3],'slot_number':r[4],'questions_used':r[5],'status':r[6]} for r in c.fetchall()]
    finally: conn.close()


def get_booking_for_user_on_date(user_id, booking_date):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''SELECT id,user_id,booking_date,slot_number,questions_used,status FROM ai_interview_bookings
                         WHERE user_id=%s AND booking_date=%s AND status IN ('booked','started','finished') LIMIT 1''',(user_id,booking_date))
            return _booking(c.fetchone())
    finally: conn.close()


def get_next_booking_for_user(user_id, today=None):
    today=today or date.today(); conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''SELECT id,user_id,booking_date,slot_number,questions_used,status FROM ai_interview_bookings
                         WHERE user_id=%s AND booking_date >= %s AND status IN ('booked','started') ORDER BY booking_date LIMIT 1''',(user_id,today))
            return _booking(c.fetchone())
    finally: conn.close()


def book_slot(user_id, booking_date, slot_number):
    if slot_number not in (1,2,3): raise ValueError('Некорректный слот')
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id,booking_date FROM ai_interview_bookings WHERE user_id=%s AND booking_date>=CURRENT_DATE AND status IN ('booked','started') LIMIT 1",(user_id,))
            existing=c.fetchone()
            if existing: raise ValueError(f'У вас уже есть активная запись на {existing[1].strftime("%d.%m.%Y")}')
            c.execute('INSERT INTO ai_interview_bookings (user_id,booking_date,slot_number) VALUES (%s,%s,%s) RETURNING id',(user_id,booking_date,slot_number))
            booking_id=c.fetchone()[0]
        conn.commit(); return booking_id
    except errors.UniqueViolation:
        conn.rollback(); raise ValueError('Этот слот уже занят')
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def cancel_booking(user_id, booking_id):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("UPDATE ai_interview_bookings SET status='cancelled' WHERE id=%s AND user_id=%s AND status='booked' AND booking_date>=CURRENT_DATE RETURNING id",(booking_id,user_id))
            row=c.fetchone()
        conn.commit(); return bool(row)
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def get_messages(booking_id):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT role,content FROM ai_interview_messages WHERE booking_id=%s AND role IN ('user','assistant') ORDER BY id",(booking_id,))
            return [{'role':r[0],'content':r[1]} for r in c.fetchall()]
    finally: conn.close()


def save_exchange(user_id, booking_id, question, answer):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT questions_used,status FROM ai_interview_bookings WHERE id=%s AND user_id=%s FOR UPDATE",(booking_id,user_id))
            row=c.fetchone()
            if not row or row[1] == 'finished': raise ValueError('Интервью недоступно')
            if row[0] >= QUESTION_LIMIT: raise ValueError('Лимит вопросов исчерпан')
            c.execute("INSERT INTO ai_interview_messages (booking_id,role,content) VALUES (%s,'user',%s),(%s,'assistant',%s)",(booking_id,question,booking_id,answer))
            c.execute("UPDATE ai_interview_bookings SET questions_used=questions_used+1,status='started' WHERE id=%s",(booking_id,))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def finish_interview(user_id, booking_id, review):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("UPDATE ai_interview_bookings SET status='finished' WHERE id=%s AND user_id=%s AND status IN ('booked','started') RETURNING id",(booking_id,user_id))
            if not c.fetchone(): raise ValueError('Интервью уже завершено или недоступно')
            c.execute("INSERT INTO ai_interview_messages (booking_id,role,content) VALUES (%s,'review',%s)",(booking_id,review))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def get_review(booking_id):
    conn=get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT content FROM ai_interview_messages WHERE booking_id=%s AND role='review' ORDER BY id DESC LIMIT 1",(booking_id,))
            row=c.fetchone(); return row[0] if row else None
    finally: conn.close()
