# soap_service.py
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel, Array, Fault
from spyne.protocol.soap import Soap11
from werkzeug.security import generate_password_hash
from psycopg2 import errors
import psycopg2
from datetime import datetime
from . import get_db  # Импортируем из основного приложения

class SoapUser(ComplexModel):
    __namespace__ = 'soap.users'
    id = Integer
    username = Unicode
    email = Unicode
    about_me = Unicode
    creation_method = Unicode

class SoapUserRequest(ComplexModel):
    __namespace__ = 'soap.users'
    username = Unicode
    email = Unicode
    password = Unicode
    about_me = Unicode(default='')

class SoapResponse(ComplexModel):
    __namespace__ = 'soap.users'
    status = Unicode
    message = Unicode
    user = SoapUser.customize(min_occurs=0)

class SoapAccountService(ServiceBase):
    @rpc(Integer, _returns=SoapUser)
    def get_user_by_id(ctx, user_id):
        """Получить пользователя по ID"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id, username, email, about_me, creation_method
                        FROM accounts 
                        WHERE id = %s
                    ''', (user_id,))
                    user = cursor.fetchone()
                    if not user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    return SoapUser(
                        id=user[0],
                        username=user[1],
                        email=user[2],
                        about_me=user[3] or '',
                        creation_method=user[4]
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(_returns=Array(SoapUser))
    def get_all_users(ctx):
        """Получить всех зайцев"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT id, username, email, about_me, creation_method
                        FROM accounts
                    ''')
                    return [
                        SoapUser(
                            id=row[0],
                            username=row[1],
                            email=row[2],
                            about_me=row[3] or '',
                            creation_method=row[4]
                        )
                        for row in cursor.fetchall()
                    ]
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')
    
    @rpc(SoapUserRequest, _returns=SoapResponse)
    def create_user(ctx, user_data):
        """Создать нового зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    password_hash = generate_password_hash(user_data.password)
                    cursor.execute('''
                        INSERT INTO accounts (username, email, password_hash, about_me, creation_method)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, username, email, about_me, creation_method
                    ''', (
                        user_data.username,
                        user_data.email,
                        password_hash,
                        user_data.about_me,
                        'soap'
                    ))
                    new_user = cursor.fetchone()
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='User created',
                        user=SoapUser(
                            id=new_user[0],
                            username=new_user[1],
                            email=new_user[2],
                            about_me=new_user[3] or '',
                            creation_method=new_user[4]
                        )
                    )
        except errors.UniqueViolation as e:
            raise Fault(faultcode='Client', faultstring='Duplicate username or email')
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_username(ctx, user_id, new_username):
        """Обновить имя зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET username = %s
                        WHERE id = %s
                        RETURNING id, username, email, about_me, creation_method
                    ''', (new_username, user_id))
                    updated_user = cursor.fetchone()
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='Username updated',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or '',
                            creation_method=updated_user[4]
                        )
                    )
        except errors.UniqueViolation as e:
            raise Fault(faultcode='Client', faultstring='Username already exists')
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_about_me(ctx, user_id, about_text):
        """Обновить информацию в поле Любимые занятия"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET about_me = %s
                        WHERE id = %s
                        RETURNING id, username, email, about_me, creation_method
                    ''', (about_text, user_id))
                    updated_user = cursor.fetchone()
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='About me updated',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or '',
                            creation_method=updated_user[4]
                        )
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_about_me(ctx, user_id):
        """Удалить информацию из поля Любимые занятия'"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        UPDATE accounts 
                        SET about_me = ''
                        WHERE id = %s
                        RETURNING id, username, email, about_me, creation_method
                    ''', (user_id,))
                    updated_user = cursor.fetchone()
                    if not updated_user:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='About me cleared',
                        user=SoapUser(
                            id=updated_user[0],
                            username=updated_user[1],
                            email=updated_user[2],
                            about_me=updated_user[3] or '',
                            creation_method=updated_user[4]
                        )
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')

    @rpc(Integer, _returns=SoapResponse)
    def delete_user(ctx, user_id):
        """Удалить зайца"""
        try:
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM accounts WHERE id = %s RETURNING id', (user_id,))
                    if cursor.rowcount == 0:
                        raise Fault(faultcode='Client', faultstring='User not found')
                    conn.commit()
                    return SoapResponse(
                        status='success',
                        message='User deleted',
                        user=None
                    )
        except psycopg2.Error as e:
            raise Fault(faultcode='Server', faultstring='Database error')
