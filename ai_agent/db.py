from datetime import date

from psycopg2 import errors

from utils.db_utils import get_db_connection


SLOTS_PER_DAY = 3
QUESTION_LIMIT = 15


def init_ai_agent_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS ai_interview_bookings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    booking_date DATE NOT NULL,
                    slot_number SMALLINT NOT NULL CHECK (slot_number BETWEEN 1 AND 3),
                    questions_used SMALLINT NOT NULL DEFAULT 0 CHECK (questions_used >= 0 AND questions_used <= 15),
                    status VARCHAR(20) NOT NULL DEFAULT 'booked',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (booking_date, slot_number),
                    UNIQUE (user_id, booking_date)
                )
                '''
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_ai_bookings_date ON ai_interview_bookings (booking_date)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_ai_bookings_user ON ai_interview_bookings (user_id, booking_date)'
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_bookings(start_date, end_date):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT b.id, b.user_id, a.username, b.booking_date, b.slot_number,
                       b.questions_used, b.status
                FROM ai_interview_bookings b
                JOIN accounts a ON a.id = b.user_id
                WHERE b.booking_date BETWEEN %s AND %s
                  AND b.status IN ('booked', 'started', 'finished')
                ORDER BY b.booking_date, b.slot_number
                ''',
                (start_date, end_date),
            )
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'user_id': row[1],
                    'username': row[2],
                    'booking_date': row[3],
                    'slot_number': row[4],
                    'questions_used': row[5],
                    'status': row[6],
                }
                for row in rows
            ]
    finally:
        conn.close()


def get_booking_for_user_on_date(user_id, booking_date):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT id, user_id, booking_date, slot_number, questions_used, status
                FROM ai_interview_bookings
                WHERE user_id = %s AND booking_date = %s
                  AND status IN ('booked', 'started', 'finished')
                LIMIT 1
                ''',
                (user_id, booking_date),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'user_id': row[1],
                'booking_date': row[2],
                'slot_number': row[3],
                'questions_used': row[4],
                'status': row[5],
            }
    finally:
        conn.close()


def get_next_booking_for_user(user_id, today=None):
    today = today or date.today()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                SELECT id, booking_date, slot_number, questions_used, status
                FROM ai_interview_bookings
                WHERE user_id = %s AND booking_date >= %s
                  AND status IN ('booked', 'started')
                ORDER BY booking_date
                LIMIT 1
                ''',
                (user_id, today),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0],
                'booking_date': row[1],
                'slot_number': row[2],
                'questions_used': row[3],
                'status': row[4],
            }
    finally:
        conn.close()


def book_slot(user_id, booking_date, slot_number):
    if slot_number not in (1, 2, 3):
        raise ValueError('Некорректный слот')

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # В MVP у пользователя может быть только одна будущая активная запись.
            cursor.execute(
                '''
                SELECT id, booking_date
                FROM ai_interview_bookings
                WHERE user_id = %s AND booking_date >= CURRENT_DATE
                  AND status IN ('booked', 'started')
                LIMIT 1
                ''',
                (user_id,),
            )
            existing = cursor.fetchone()
            if existing:
                raise ValueError(f'У вас уже есть активная запись на {existing[1].strftime("%d.%m.%Y")}')

            cursor.execute(
                '''
                INSERT INTO ai_interview_bookings (user_id, booking_date, slot_number)
                VALUES (%s, %s, %s)
                RETURNING id
                ''',
                (user_id, booking_date, slot_number),
            )
            booking_id = cursor.fetchone()[0]
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
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE ai_interview_bookings
                SET status = 'cancelled'
                WHERE id = %s AND user_id = %s AND status = 'booked'
                  AND booking_date >= CURRENT_DATE
                RETURNING id
                ''',
                (booking_id, user_id),
            )
            row = cursor.fetchone()
        conn.commit()
        return bool(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
