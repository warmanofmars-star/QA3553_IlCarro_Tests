import random
import string
import json  # Добавили
import os    # Добавили
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

        # Добиваем длину до 9 символов случайными буквами/цифрами
        rest = ''.join(random.choices(string.ascii_letters + string.digits, k=5))

        password_list = list(upper + lower + digit + special + rest)
        random.shuffle(password_list)

        return ''.join(password_list)

    @classmethod
    def get_random_user(cls, **overrides) -> User:
        """
        Генерирует случайного валидного юзера.
        Позволяет точечно ломать любые поля через **overrides.
        Например: get_random_user(name="")
        """
        data = {
            "name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),  # Уникальный email "из коробки", uuid больше не нужен
            "password": cls.generate_valid_password()
        }

        # Если мы передали какие-то кривые данные для негативного теста - заменяем ими валидные
        data.update(overrides)

        # Распаковываем словарь прямо в модель User
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

        # Сохраняем в папку logs, так как она уже гарантированно создается нашим логгером
        filepath = os.path.join("logs", "registered_users.jsonl")

        # Режим 'a' (append) безопасно дописывает строку в конец файла
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(user_data) + "\n")


class SearchDataGenerator:
    # Запасной список на случай, если бэкенд недоступен
    FALLBACK_CITIES = ["Tel Aviv", "Jerusalem", "Haifa"]

    # Список, который мы вытащили из фронтенда (JS-код)
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
        try:
            api = IlCarroAPI()
            response = api.get_cities()

            if response.status_code == 200:
                api_cities = [city_obj.get("city") for city_obj in response.json().get("cities", [])]

                # Используем cls.UI_CITIES для обращения к константе класса
                safe_cities = list(set(api_cities).intersection(set(cls.UI_CITIES)))

                if safe_cities:
                    return random.choice(safe_cities)
        except Exception as e:
            logger.error(f"Не удалось получить города из API. Ошибка: {e}") # <-- Заменили print

        logger.warning(f"Используем fallback-города: {cls.FALLBACK_CITIES}")  # <-- Добавили логирование fallback'а
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

    # Берем безопасные списки как в учебном проекте, чтобы избежать скрытых багов длины строки
    MAKE_TYPES = ["Toyota", "Honda", "Ford", "BMW", "Mazda"]
    MODEL_TYPES = ["Camry", "Civic", "Focus", "X5", "Premium"]
    CLASS_TYPES = ["Economy", "Comfort", "Business", "Premium"]

    @staticmethod
    def get_random_car(**overrides) -> Car:
        """Генерирует случайную машину. Позволяет переопределять любые поля через **overrides"""
        # Базовые случайные данные (используем Faker и твои списки)
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
            "reg_number": fake.unique.bothify(text='??-###-??').upper(),
            "price": str(random.randint(100, 1000)),
            "about": fake.sentence(),
            "photo_path": None
        }

        # Накатываем сверху те значения, которые мы передали в тест (если они есть)
        data.update(overrides)

        # Распаковываем словарь в наш красивый датакласс Car!
        return Car(**data)