import random
from flask import Blueprint, jsonify, render_template, request, session, url_for
from utils.db_utils import get_db_connection
from main.routes import login_required


tic_tac_toe_bp = Blueprint('tic_tac_toe', __name__)

WIN_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def _winner(board):
    for a, b, c in WIN_LINES:
        if board[a] != '-' and board[a] == board[b] == board[c]:
            return board[a]
    return None


def _status(board):
    winner = _winner(board)
    if winner == 'X':
        return 'player_won', 'player', None
    if winner == 'O':
        return 'bot_won', 'bot', None
    if '-' not in board:
        return 'draw', None, None
    return 'active', None, 'player'


def _bot_move(board):
    free = [i for i, value in enumerate(board) if value == '-']
    if not free:
        return board

    for symbol in ('O', 'X'):
        for cell in free:
            probe = list(board)
            probe[cell] = symbol
            if _winner(probe) == symbol:
                result = list(board)
                result[cell] = 'O'
                return result

    preferred = [cell for cell in (4, 0, 2, 6, 8) if cell in free]
    cell = random.choice(preferred or free)
    result = list(board)
    result[cell] = 'O'
    return result


def _game_payload(row):
    game_id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at = row
    return {
        'game_id': game_id,
        'user_id': user_id,
        'board': [None if cell == '-' else cell for cell in board],
        'status': status,
        'winner': winner,
        'next_turn': next_turn,
        'moves_count': moves_count,
        'player_symbol': 'X',
        'bot_symbol': 'O',
        'created_at': created_at.isoformat() if created_at else None,
        'updated_at': updated_at.isoformat() if updated_at else None,
        'visualization_url': url_for('tic_tac_toe.game_view', game_id=game_id, _external=True),
    }


def _fetch_game(cursor, game_id):
    cursor.execute(
        """
        SELECT id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at
        FROM tic_tac_toe_games WHERE id = %s
        """,
        (game_id,),
    )
    return cursor.fetchone()


@tic_tac_toe_bp.route('/')
@login_required
def index():
    return render_template(
        'tic_tac_toe.html',
        username=session.get('username'),
        user_id=session.get('user_id'),
    )


@tic_tac_toe_bp.route('/game/<int:game_id>')
@login_required
def game_view(game_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            row = _fetch_game(cursor, game_id)
            if not row:
                return render_template('errors/404.html'), 404
            if row[1] != session.get('user_id'):
                return render_template('access_denied.html'), 403
            return render_template('tic_tac_toe_game.html', game_id=game_id, user_id=session.get('user_id'))
    finally:
        conn.close()


@tic_tac_toe_bp.route('/api/users/<int:user_id>/games', methods=['POST'])
def create_game(user_id):
    """
    Создать новую партию крестиков-ноликов для пользователя.
    ---
    tags:
      - Tic Tac Toe REST
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
        description: ID пользователя из accounts
    responses:
      201:
        description: Партия создана. В ответе есть game_id и visualization_url.
      404:
        description: Пользователь не найден.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM accounts WHERE id = %s', (user_id,))
            if not cursor.fetchone():
                return jsonify(error='USER_NOT_FOUND', message='User not found'), 404

            cursor.execute(
                """
                INSERT INTO tic_tac_toe_games (user_id)
                VALUES (%s)
                RETURNING id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            conn.commit()
            return jsonify(_game_payload(row)), 201
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@tic_tac_toe_bp.route('/api/users/<int:user_id>/games/<int:game_id>', methods=['GET'])
def get_game(user_id, game_id):
    """
    Получить текущее состояние поля и статус партии.
    ---
    tags:
      - Tic Tac Toe REST
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
      - in: path
        name: game_id
        required: true
        type: integer
    responses:
      200:
        description: Состояние партии, поле, статус, победитель и чей следующий ход.
      403:
        description: Партия принадлежит другому пользователю.
      404:
        description: Партия не найдена.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            row = _fetch_game(cursor, game_id)
            if not row:
                return jsonify(error='GAME_NOT_FOUND', message='Game not found'), 404
            if row[1] != user_id:
                return jsonify(error='FORBIDDEN', message='This game belongs to another user'), 403
            return jsonify(_game_payload(row)), 200
    finally:
        conn.close()


@tic_tac_toe_bp.route('/api/users/<int:user_id>/games/<int:game_id>/moves', methods=['POST'])
def make_move(user_id, game_id):
    """
    Сделать ход крестиком. После принятого хода сервер автоматически ходит ноликом.
    ---
    tags:
      - Tic Tac Toe REST
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
      - in: path
        name: game_id
        required: true
        type: integer
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [cell]
          properties:
            cell:
              type: array
              minItems: 2
              maxItems: 2
              items:
                type: integer
                minimum: 0
                maximum: 2
              example: [1, 1]
              description: Координаты клетки [row, column], индексы от 0 до 2.
    responses:
      200:
        description: Ход принят; возвращается новое состояние партии после ответа сервера.
      400:
        description: Некорректный JSON или координаты клетки.
      403:
        description: Партия принадлежит другому пользователю.
      404:
        description: Партия не найдена.
      409:
        description: Партия завершена или клетка уже занята.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or 'cell' not in data:
        return jsonify(error='BAD_REQUEST', message='JSON body with field "cell": [row, column] is required'), 400

    cell = data.get('cell')
    if (
        not isinstance(cell, list)
        or len(cell) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in cell)
    ):
        return jsonify(error='BAD_REQUEST', message='cell must be an array [row, column]'), 400

    row_index, column_index = cell
    if not (0 <= row_index <= 2 and 0 <= column_index <= 2):
        return jsonify(error='BAD_REQUEST', message='row and column must be integers from 0 to 2'), 400

    board_index = row_index * 3 + column_index

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at
                FROM tic_tac_toe_games WHERE id = %s FOR UPDATE
                """,
                (game_id,),
            )
            row = cursor.fetchone()
            if not row:
                return jsonify(error='GAME_NOT_FOUND', message='Game not found'), 404
            if row[1] != user_id:
                return jsonify(error='FORBIDDEN', message='This game belongs to another user'), 403
            if row[3] != 'active':
                return jsonify(error='GAME_FINISHED', message='The game is already finished'), 409

            board = list(row[2])
            if board[board_index] != '-':
                return jsonify(error='CELL_OCCUPIED', message='This cell is already occupied'), 409

            board[board_index] = 'X'
            status, winner, next_turn = _status(board)
            moves_count = row[6] + 1

            if status == 'active':
                board = _bot_move(board)
                moves_count += 1
                status, winner, next_turn = _status(board)

            cursor.execute(
                """
                UPDATE tic_tac_toe_games
                SET board = %s, status = %s, winner = %s, next_turn = %s,
                    moves_count = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at
                """,
                (''.join(board), status, winner, next_turn, moves_count, game_id),
            )
            updated = cursor.fetchone()
            conn.commit()
            return jsonify(_game_payload(updated)), 200
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@tic_tac_toe_bp.route('/api/users/<int:user_id>/games', methods=['GET'])
def list_games(user_id):
    """
    Получить список партий пользователя.
    ---
    tags:
      - Tic Tac Toe REST
    parameters:
      - in: path
        name: user_id
        required: true
        type: integer
    responses:
      200:
        description: Все партии пользователя, включая несколько активных одновременно.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, board, status, winner, next_turn, moves_count, created_at, updated_at
                FROM tic_tac_toe_games
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
            return jsonify(games=[_game_payload(row) for row in cursor.fetchall()]), 200
    finally:
        conn.close()
