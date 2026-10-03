import random
import uuid
from pathlib import Path
import string
import json
import os
from datetime import datetime, timedelta
from faker import Faker

from models.user import User
from api.car_api import IlCarroAPI
from models.car import Car
from utils.logger import get_logger

logger = get_logger("DATA")

# Инициализируем Faker один раз
fake = Faker('en_US')


class UserGenerator:

    @staticmethod
    def generate_valid_password():
        """Генерирует валидный пароль: минимум 8 символов, 1 большая, 1 маленькая, 1 цифра, 1 спецсимвол"""
        upper = random.choice(string.ascii_uppercase)
        lower = random.choice(string.ascii_lowercase)
        digit = random.choice(string.digits)
        special = random.choice("@$#^&*!")

        rest = ''.join(random.choices(string.ascii_letters + string.digits, k=5))

        password_list = list(upper + lower + digit + special + rest)
        random.shuffle(password_list)

        return ''.join(password_list)

    @staticmethod
    def generate_valid_email():
        """Генерирует абсолютно уникальный email, безопасный для xdist и БД"""
        # uuid4() дает уникальную строку, вероятность повторения которой стремится к нулю
        unique_id = uuid.uuid4().hex[:10]
        return f"user_{unique_id}@example.com"

    @classmethod
    def get_random_user(cls, **overrides) -> User:
        """
        Генерирует случайного валидного юзера.
        """
        data = {
            "name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": cls.generate_valid_email(),  # ЗАМЕНИЛИ FAKER НА UUID
            "password": cls.generate_valid_password()
        }

        data.update(overrides)
        return User(**data)

    @staticmethod
    def save_created_user(user: User):
        """Сохраняет данные успешно зарегистрированного пользователя в файл."""
        user_data = {
            "name": user.name,
            "last_name": user.last_name,
            "email": user.email,
            "password": user.password
        }

        project_root = Path(__file__).resolve().parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)

        filepath = log_dir / "registered_users.jsonl"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(user_data) + "\n")


class SearchDataGenerator:
    FALLBACK_CITIES = ["Tel Aviv", "Jerusalem", "Haifa"]

    # Сюда мы сохраним результат первого успешного запроса к API
    _cached_safe_cities = None

    UI_CITIES = [
        "Tel Aviv", "Jerusalem", "Haifa", "Rishon LeZion", "Petah Tikva", "Ashdod",
        "Netanya", "Beersheba", "Bnei Brak", "Holon", "Ramat Gan", "Ashkelon",
        "Rehovot", "Bat Yam", "Beit Shemesh", "Kfar Saba", "Herzliya", "Hadera",
        "Modi'in-Maccabim-Re'ut", "Nazareth", "Lod", "Ramla", "Ra'anana",
        "Rosh HaAyin", "Acre", "Eilat", "Kiryat Ata", "Kiryat Gat", "Kiryat Yam",
        "Kiryat Motzkin", "Kiryat Bialik", "Nahariya", "Tiberias", "Safed", "Afula",
        "Carmiel", "Nes Ziona", "Yavne", "Or Yehuda", "Givatayim", "Kiryat Ono",
        "Umm al-Fahm", "Sakhnin", "Tamra", "Tayibe", "Tira", "Ma'alot-Tarshiha",
        "Migdal HaEmek", "Sderot", "Arad", "Dimona", "Ofakim", "Yeruham", "Kiryat Shmona"
    ]

    @classmethod
    def get_random_city(cls):
        # 1. Если список уже есть в памяти (кеш), отдаем его мгновенно без сети!
        if cls._cached_safe_cities:
            return random.choice(cls._cached_safe_cities)

        # 2. Если кеш пуст, делаем один запрос
        try:
            api = IlCarroAPI()
            response = api.get_cities()

            if response.status_code == 200:
                api_cities = [city_obj.get("city") for city_obj in response.json().get("cities", [])]
                safe_cities = list(set(api_cities).intersection(set(cls.UI_CITIES)))

                if safe_cities:
                    # Сохраняем в кеш для всех будущих вызовов
                    cls._cached_safe_cities = safe_cities
                    return random.choice(cls._cached_safe_cities)
        except Exception as e:
            logger.error(f"Не удалось получить города из API. Ошибка: {e}")

        logger.warning(f"Используем fallback-города: {cls.FALLBACK_CITIES}")
        return random.choice(cls.FALLBACK_CITIES)

    @staticmethod
    def get_safe_future_dates(min_offset=1, max_offset=10, min_duration=2, max_duration=6):
        today = datetime.now()
        start_offset = random.randint(min_offset, max_offset)
        start_date = today + timedelta(days=start_offset)
        duration = random.randint(min_duration, max_duration)
        end_date = start_date + timedelta(days=duration)
        return start_date, end_date


class CarGenerator:
    FUEL_TYPES = ["Petrol", "Diesel", "Hybrid", "Electric"]
    GEAR_TYPES = ["Automatic", "Manual"]
    WD_TYPES = ["AWD", "FWD", "RWD"]

    MAKE_TYPES = ["Toyota", "Honda", "Ford", "BMW", "Mazda"]
    MODEL_TYPES = ["Camry", "Civic", "Focus", "X5", "Premium"]
    CLASS_TYPES = ["Economy", "Comfort", "Business", "Premium"]

    @staticmethod
    def get_random_car(**overrides) -> Car:
        data = {
            "city": SearchDataGenerator.get_random_city(),
            "make": fake.company(),
            "model": fake.word().capitalize(),
            "year": str(random.randint(2010, 2024)),
            "fuel": random.choice(["Petrol", "Diesel", "Hybrid", "Electric"]),
            "gear": random.choice(["Manual", "Automatic"]),
            "wd": random.choice(["AWD", "FWD", "RWD"]),
            "doors": str(random.randint(2, 5)),
            "seats": str(random.randint(2, 7)),
            "car_class": random.choice(["Economy", "Business", "Premium"]),
            "reg_number": f"IL-{uuid.uuid4().hex[:8].upper()}",
            "price": str(random.randint(100, 1000)),
            "about": fake.sentence(),
            "photo_path": None
        }

        data.update(overrides)
        return Car(**data)