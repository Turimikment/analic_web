# soap_service.py
from spyne import Application, rpc, ServiceBase, Unicode, Integer, ComplexModel, Array, Fault
from spyne.protocol.soap import Soap11
import db_utils
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            user = db_utils.get_account_by_id(user_id)
            if not user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapUser(
                id=user['id'],
                username=user['username'],
                email=user['email'],
                about_me=user['about_me'] or '',
                creation_method=user['creation_method']
            )
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(_returns=Array(SoapUser))
    def get_all_users(ctx):
        """Получить всех пользователей"""
        try:
            users = db_utils.get_all_accounts()
            return [
                SoapUser(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    about_me=user['about_me'] or '',
                    creation_method=user['creation_method']
                )
                for user in users
            ]
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')
    
    @rpc(SoapUserRequest, _returns=SoapResponse)
    def create_user(ctx, user_data):
        """Создать нового пользователя"""
        try:
            logger.info(f"SOAP create_user: {user_data.username}, {user_data.email}")
            new_user = db_utils.create_account(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,
                creation_method='soap',
                about_me=user_data.about_me
            )
            soap_user = SoapUser(
                id=new_user['id'],
                username=new_user['username'],
                email=new_user['email'],
                about_me=new_user['about_me'] or '',
                creation_method=new_user['creation_method']
            )
            return SoapResponse(
                status='success',
                message='User created',
                user=soap_user
            )
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise Fault(faultcode='Client', faultstring=str(e))
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_username(ctx, user_id, new_username):
        """Обновить имя пользователя"""
        try:
            updated_user = db_utils.update_username(user_id, new_username)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='Username updated',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise Fault(faultcode='Client', faultstring=str(e))
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(Integer, Unicode, _returns=SoapResponse)
    def update_about_me(ctx, user_id, about_text):
        """Обновить информацию 'О себе'"""
        try:
            updated_user = db_utils.update_about_me(user_id, about_text)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='About me updated',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(Integer, _returns=SoapResponse)
    def delete_about_me(ctx, user_id):
        """Удалить информацию 'О себе'"""
        try:
            updated_user = db_utils.delete_about_me(user_id)
            if not updated_user:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='About me cleared',
                user=SoapUser(
                    id=updated_user['id'],
                    username=updated_user['username'],
                    email=updated_user['email'],
                    about_me=updated_user['about_me'] or '',
                    creation_method=updated_user['creation_method']
                )
            )
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

    @rpc(Integer, _returns=SoapResponse)
    def delete_user(ctx, user_id):
        """Удалить пользователя"""
        try:
            success = db_utils.delete_account(user_id)
            if not success:
                raise Fault(faultcode='Client', faultstring='User not found')
            return SoapResponse(
                status='success',
                message='User deleted',
                user=None
            )
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise Fault(faultcode='Server', faultstring=f'Database error: {str(e)}')

# Создание SOAP приложения
soap_app = Application(
    [SoapAccountService],
    tns='soap.users',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)