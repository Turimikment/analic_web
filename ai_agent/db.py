from datetime import date
from psycopg2 import errors
from utils.db_utils import get_db_connection

SLOTS_PER_DAY = 2
QUESTION_LIMIT = 24
AGENT_IDS = ('business', 'developer')


def init_ai_agent_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS ai_interview_bookings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    booking_date DATE NOT NULL,
                    slot_number SMALLINT NOT NULL CHECK(slot_number BETWEEN 1 AND 3),
                    questions_used SMALLINT NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'booked',
                    request_in_flight BOOLEAN NOT NULL DEFAULT FALSE,
                    request_started_at TIMESTAMP NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(booking_date, slot_number),
                    UNIQUE(user_id, booking_date)
                )
            ''')
            c.execute("ALTER TABLE ai_interview_bookings ADD COLUMN IF NOT EXISTS request_in_flight BOOLEAN NOT NULL DEFAULT FALSE")
            c.execute("ALTER TABLE ai_interview_bookings ADD COLUMN IF NOT EXISTS request_started_at TIMESTAMP NULL")
            c.execute("UPDATE ai_interview_bookings SET request_in_flight=FALSE, request_started_at=NULL WHERE request_in_flight=TRUE OR request_started_at IS NOT NULL")

            # Cancelled rows were hidden from the calendar but still occupied the
            # UNIQUE(date, slot) key. Remove legacy cancelled bookings so a slot
            # that looks free is actually bookable again.
            c.execute("DELETE FROM ai_interview_bookings WHERE status='cancelled'")

            c.execute('''DO $$ DECLARE r record; BEGIN
                FOR r IN SELECT conname FROM pg_constraint
                    WHERE conrelid='ai_interview_bookings'::regclass AND contype='c'
                    AND pg_get_constraintdef(oid) ILIKE '%questions_used%15%'
                LOOP EXECUTE format('ALTER TABLE ai_interview_bookings DROP CONSTRAINT %I',r.conname); END LOOP;
            END $$''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS ai_interview_messages (
                    id SERIAL PRIMARY KEY,
                    booking_id INTEGER NOT NULL REFERENCES ai_interview_bookings(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL CHECK(role IN ('user','assistant','review')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute("ALTER TABLE ai_interview_messages ADD COLUMN IF NOT EXISTS agent VARCHAR(20) NOT NULL DEFAULT 'business'")
            c.execute('''
                CREATE TABLE IF NOT EXISTS ai_interview_specs (
                    id SERIAL PRIMARY KEY,
                    booking_id INTEGER NOT NULL REFERENCES ai_interview_bookings(id) ON DELETE CASCADE,
                    mermaid TEXT NOT NULL DEFAULT '',
                    api_spec TEXT NOT NULL DEFAULT '',
                    business_rules TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_ai_bookings_date ON ai_interview_bookings(booking_date)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_ai_messages_booking ON ai_interview_messages(booking_id,id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_ai_specs_booking ON ai_interview_specs(booking_id,id)')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _booking(row):
    if not row:
        return None
    return {
        'id': row[0], 'user_id': row[1], 'booking_date': row[2],
        'slot_number': row[3], 'questions_used': row[4], 'status': row[5]
    }


def get_bookings(start_date, end_date):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''
                SELECT b.id,b.user_id,a.username,b.booking_date,b.slot_number,b.questions_used,b.status
                FROM ai_interview_bookings b
                JOIN accounts a ON a.id=b.user_id
                WHERE b.booking_date BETWEEN %s AND %s
                  AND b.status IN ('booked','started','finished')
                ORDER BY b.booking_date,b.slot_number
            ''', (start_date, end_date))
            return [
                {'id':r[0],'user_id':r[1],'username':r[2],'booking_date':r[3],
                 'slot_number':r[4],'questions_used':r[5],'status':r[6]}
                for r in c.fetchall()
            ]
    finally:
        conn.close()


def get_booking_for_user_on_date(user_id, booking_date):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('''
                SELECT b.id,b.user_id,b.booking_date,b.slot_number,
                       COUNT(m.id) FILTER(WHERE m.role='user')::int,b.status
                FROM ai_interview_bookings b
                LEFT JOIN ai_interview_messages m ON m.booking_id=b.id
                WHERE b.user_id=%s AND b.booking_date=%s
                  AND b.status IN ('booked','started','finished')
                GROUP BY b.id,b.user_id,b.booking_date,b.slot_number,b.status
                LIMIT 1
            ''', (user_id, booking_date))
            return _booking(c.fetchone())
    finally:
        conn.close()


def get_next_booking_for_user(user_id, today=None):
    today = today or date.today()
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id,user_id,booking_date,slot_number,questions_used,status FROM ai_interview_bookings WHERE user_id=%s AND booking_date>=%s AND status IN ('booked','started') ORDER BY booking_date LIMIT 1", (user_id, today))
            return _booking(c.fetchone())
    finally:
        conn.close()


def book_slot(user_id, booking_date, slot_number):
    if slot_number not in (1, 2):
        raise ValueError('Некорректный слот')
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id,booking_date FROM ai_interview_bookings WHERE user_id=%s AND booking_date>=CURRENT_DATE AND status IN ('booked','started') LIMIT 1", (user_id,))
            existing = c.fetchone()
            if existing:
                raise ValueError(f'У тебя уже есть активная запись на {existing[1].strftime("%d.%m.%Y")}')
            c.execute('INSERT INTO ai_interview_bookings(user_id,booking_date,slot_number) VALUES(%s,%s,%s) RETURNING id', (user_id, booking_date, slot_number))
            booking_id = c.fetchone()[0]
        conn.commit()
        return booking_id
    except errors.UniqueViolation:
        conn.rollback()
        raise ValueError('Этот слот уже занят')
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_booking(user_id, booking_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            # Cancellation frees the UNIQUE(date, slot) key immediately.
            c.execute("DELETE FROM ai_interview_bookings WHERE id=%s AND user_id=%s AND status='booked' AND booking_date>=CURRENT_DATE RETURNING id", (booking_id,user_id))
            row = c.fetchone()
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_messages(booking_id, agent=None):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            if agent:
                c.execute("SELECT role,content,agent FROM ai_interview_messages WHERE booking_id=%s AND role IN ('user','assistant') AND agent=%s ORDER BY id", (booking_id,agent))
            else:
                c.execute("SELECT role,content,agent FROM ai_interview_messages WHERE booking_id=%s AND role IN ('user','assistant') ORDER BY id", (booking_id,))
            return [{'role':r[0],'content':r[1],'agent':r[2]} for r in c.fetchall()]
    finally:
        conn.close()


def get_latest_spec(booking_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT mermaid,api_spec,business_rules FROM ai_interview_specs WHERE booking_id=%s ORDER BY id DESC LIMIT 1', (booking_id,))
            r = c.fetchone()
            return {'mermaid':r[0],'api_spec':r[1],'business_rules':r[2]} if r else {'mermaid':'','api_spec':'','business_rules':''}
    finally:
        conn.close()


def save_spec(user_id, booking_id, mermaid, api_spec, business_rules):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT id FROM ai_interview_bookings WHERE id=%s AND user_id=%s AND status IN ('booked','started')", (booking_id,user_id))
            if not c.fetchone():
                raise ValueError('Симуляция недоступна')
            c.execute('INSERT INTO ai_interview_specs(booking_id,mermaid,api_spec,business_rules) VALUES(%s,%s,%s,%s)', (booking_id,mermaid,api_spec,business_rules))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_exchange(user_id, booking_id, agent, question, answer):
    if agent not in AGENT_IDS:
        raise ValueError('Неизвестный собеседник')
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute('SELECT status FROM ai_interview_bookings WHERE id=%s AND user_id=%s FOR UPDATE', (booking_id,user_id))
            row = c.fetchone()
            if not row or row[0] == 'finished':
                raise ValueError('Симуляция недоступна')
            c.execute("SELECT COUNT(*) FROM ai_interview_messages WHERE booking_id=%s AND role='user'", (booking_id,))
            used = c.fetchone()[0]
            if used >= QUESTION_LIMIT:
                raise ValueError('Лимит сообщений исчерпан')
            c.execute("INSERT INTO ai_interview_messages(booking_id,role,content,agent) VALUES(%s,'user',%s,%s),(%s,'assistant',%s,%s)", (booking_id,question,agent,booking_id,answer,agent))
            c.execute("UPDATE ai_interview_bookings SET questions_used=%s,status='started',request_in_flight=FALSE,request_started_at=NULL WHERE id=%s", (used+1,booking_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def finish_interview(user_id, booking_id, review):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("UPDATE ai_interview_bookings SET status='finished',request_in_flight=FALSE,request_started_at=NULL WHERE id=%s AND user_id=%s AND status IN ('booked','started') RETURNING id", (booking_id,user_id))
            if not c.fetchone():
                raise ValueError('Симуляция уже завершена или недоступна')
            c.execute("INSERT INTO ai_interview_messages(booking_id,role,content,agent) VALUES(%s,'review',%s,'review')", (booking_id,review))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_review(booking_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT content FROM ai_interview_messages WHERE booking_id=%s AND role='review' ORDER BY id DESC LIMIT 1", (booking_id,))
            r = c.fetchone()
            return r[0] if r else None
    finally:
        conn.close()
