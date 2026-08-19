from utils.db_utils import get_db_connection


def init_tic_tac_toe_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tic_tac_toe_games (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    board VARCHAR(9) NOT NULL DEFAULT '---------',
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    winner VARCHAR(10),
                    next_turn VARCHAR(10) DEFAULT 'player',
                    moves_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
