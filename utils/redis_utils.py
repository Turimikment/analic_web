
import redis
import random
import os
import logging
from datetime import datetime, timedelta

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CarrotStats:
    def __init__(self):
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        logger.info(f"Connecting to Redis at: {redis_url}")
        
        # Для Redis в облаке (использует SSL)
        if redis_url.startswith('rediss://'):
            self.redis = redis.from_url(redis_url, ssl_cert_reqs=None)
        else:
            self.redis = redis.from_url(redis_url)
            
        self.usernames = [
            "Быстрый Заяц", "Ушастик", "Морковкин", "Прыгун", 
            "Пушистик", "Шустрик", "Хвостик", "Рыжик", "Снежок"
        ]

    def get_stats(self):
        """Получение статистики по морковкам"""
        try:
            # Получаем общее количество морковок
            total_carrots = self.redis.get('total_carrots') or 0
            
            # Получаем рекорд за день
            top_user = self.redis.get('daily_record') or 0
            
            # Получаем среднее время сбора
            avg_time = self.redis.get('avg_collect_time') or 0
            
            # Получаем топ-5 пользователей за день
            today = datetime.now().strftime('%Y-%m-%d')
            top_users_key = f"top_users:{today}"
            top_users = []
            
            # Получаем топ-5 из сортированного множества
            users_data = self.redis.zrevrange(top_users_key, 0, 4, withscores=True)
            for username, score in users_data:
                top_users.append({
                    'username': username.decode('utf-8'),
                    'carrots': int(score)
                })
            
            return {
                'total_carrots': int(total_carrots),
                'top_user': int(top_user),
                'avg_time': float(avg_time),
                'top_users': top_users
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                'total_carrots': 0,
                'top_user': 0,
                'avg_time': 0,
                'top_users': []
            }

    def collect_carrot(self):
        """Сбор морковки случайным зайцем"""
        try:
            username = random.choice(self.usernames)
            
            # Обновляем общее количество
            self.redis.incr('total_carrots')
            
            # Обновляем дневную статистику
            today = datetime.now().strftime('%Y-%m-%d')
            user_key = f"user_carrots:{today}:{username}"
            user_carrots = self.redis.incr(user_key)
            
            # Добавляем в сортированное множество для топа
            top_users_key = f"top_users:{today}"
            self.redis.zincrby(top_users_key, 1, username)
            
            # Обновляем рекорд за день
            current_record = int(self.redis.get('daily_record') or 0)
            if user_carrots > current_record:
                self.redis.set('daily_record', user_carrots)
            
            # Обновляем среднее время сбора (демо)
            avg_time = float(self.redis.get('avg_collect_time') or 0)
            new_avg = (avg_time + random.uniform(0.5, 2.0)) / 2
            self.redis.set('avg_collect_time', new_avg)
            
            return {
                'status': 'success',
                'message': f'{username} собрал морковку!',
                'total': int(self.redis.get('total_carrots') or 0)
            }
        except Exception as e:
            logger.error(f"Error collecting carrot: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка: {e}'
            }

    def reset_stats(self):
        """Сброс всей статистики по морковкам"""
        try:
            # Удаляем основные ключи
            keys = [
                'total_carrots',
                'daily_record',
                'avg_collect_time'
            ]
            
            # Удаляем ключи топов за последние 7 дней
            today = datetime.now()
            for i in range(7):
                date_str = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                keys.append(f"top_users:{date_str}")
                
                # Удаляем ключи пользователей за этот день
                user_keys = self.redis.keys(f"user_carrots:{date_str}:*")
                if user_keys:
                    self.redis.delete(*user_keys)
            
            # Удаляем все найденные ключи
            if keys:
                self.redis.delete(*keys)
            
            return {
                'status': 'success',
                'message': 'Статистика по морковкам сброшена!'
            }
        except Exception as e:
            logger.error(f"Error resetting stats: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка: {e}'
            }