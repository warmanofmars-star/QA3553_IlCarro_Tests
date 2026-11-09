import logging
import random
import string
import uuid
from datetime import datetime, timedelta

from faker import Faker

from api.car_api import IlCarroAPI
from models.car import Car
from models.user import User

logger = logging.getLogger(__name__)

# Инициализируем Faker один раз
fake = Faker("en_US")


class UserGenerator:
    @staticmethod
    def generate_valid_password():
        """Генерирует валидный пароль: минимум 8 символов, 1 большая, 1 маленькая, 1 цифра, 1 спецсимвол"""
        upper = random.choice(string.ascii_uppercase)
        lower = random.choice(string.ascii_lowercase)
        digit = random.choice(string.digits)
        special = random.choice("@$#^&*!")

        rest = "".join(random.choices(string.ascii_letters + string.digits, k=5))

        password_list = list(upper + lower + digit + special + rest)
        random.shuffle(password_list)

        return "".join(password_list)

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
            "password": cls.generate_valid_password(),
        }

        data.update(overrides)
        return User(**data)


class SearchDataGenerator:
    FALLBACK_CITIES = ["Tel Aviv", "Jerusalem", "Haifa"]

    # Город с малым числом машин для UI-поиска (Q-UI-12: 16 машин). Ответ поиска по крупному
    # городу весит десятки мегабайт (Tel Aviv — около 18 МБ, Q-API-02), а нашу машину среди тысяч
    # карточек на экране не найти. Город есть и во фронтенде, и в API (см. get_safe_cities).
    SMALL_CITY = "Sderot"

    # Сюда мы сохраним результат первого успешного запроса к API
    _cached_safe_cities = None

    UI_CITIES = [
        "Tel Aviv",
        "Jerusalem",
        "Haifa",
        "Rishon LeZion",
        "Petah Tikva",
        "Ashdod",
        "Netanya",
        "Beersheba",
        "Bnei Brak",
        "Holon",
        "Ramat Gan",
        "Ashkelon",
        "Rehovot",
        "Bat Yam",
        "Beit Shemesh",
        "Kfar Saba",
        "Herzliya",
        "Hadera",
        "Modi'in-Maccabim-Re'ut",
        "Nazareth",
        "Lod",
        "Ramla",
        "Ra'anana",
        "Rosh HaAyin",
        "Acre",
        "Eilat",
        "Kiryat Ata",
        "Kiryat Gat",
        "Kiryat Yam",
        "Kiryat Motzkin",
        "Kiryat Bialik",
        "Nahariya",
        "Tiberias",
        "Safed",
        "Afula",
        "Carmiel",
        "Nes Ziona",
        "Yavne",
        "Or Yehuda",
        "Givatayim",
        "Kiryat Ono",
        "Umm al-Fahm",
        "Sakhnin",
        "Tamra",
        "Tayibe",
        "Tira",
        "Ma'alot-Tarshiha",
        "Migdal HaEmek",
        "Sderot",
        "Arad",
        "Dimona",
        "Ofakim",
        "Yeruham",
        "Kiryat Shmona",
    ]

    @classmethod
    def get_safe_cities(cls) -> list[str]:
        """Города, пригодные для позитивных тестов: те, что есть И в подсказке фронтенда, И в API.

        Почему пересечение, а не один из списков (DISC-02 в docs/requirements/requirements.md):
        списки городов фронтенда (54) и API (37) расходятся, общих только 22, и написание разное
        (Beersheba / Beer Sheva, Kiryat … / Qiryat …).
          * Город только из фронтенда UI-форма предложит, но API машину с ним не создаст
            («Failed to submit car», Q-UI-03), а поиск по нему молча пуст (Q-UI-12).
          * Город только из API в подсказке формы не найдётся — UI-тест не сможет его выбрать.
        Позитивный тест должен проходить по обоим путям, поэтому берём только общие города.
        Само расхождение проверяет отдельный тест (known_bug CITIES_MISMATCH), здесь его обходим.
        """
        # 1. Список уже есть в памяти (кеш) — отдаем его без сети
        if cls._cached_safe_cities:
            return cls._cached_safe_cities

        # 2. Если кеш пуст, делаем один запрос
        try:
            api = IlCarroAPI()
            response = api.get_cities()

            if response.status_code == 200:
                api_cities = [city_obj.get("city") for city_obj in response.json().get("cities", [])]
                # sorted: порядок set не детерминирован, а одинаковый список удобнее в отладке
                safe_cities = sorted(set(api_cities).intersection(cls.UI_CITIES))

                if safe_cities:
                    # Сохраняем в кеш для всех будущих вызовов
                    cls._cached_safe_cities = safe_cities
                    return cls._cached_safe_cities
        except Exception as e:
            logger.error(f"Не удалось получить города из API. Ошибка: {e}")

        logger.warning(f"Используем fallback-города: {cls.FALLBACK_CITIES}")
        return cls.FALLBACK_CITIES

    @classmethod
    def get_random_city(cls):
        return random.choice(cls.get_safe_cities())

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
    CLASS_TYPES = ["Economy", "Business", "Premium"]

    @classmethod
    def get_random_car(cls, **overrides) -> Car:
        data = {
            "city": SearchDataGenerator.get_random_city(),
            "make": fake.company(),
            "model": fake.word().capitalize(),
            "year": str(random.randint(2010, 2024)),
            "fuel": random.choice(cls.FUEL_TYPES),
            "gear": random.choice(cls.GEAR_TYPES),
            "wd": random.choice(cls.WD_TYPES),
            "doors": str(random.randint(2, 5)),
            "seats": str(random.randint(2, 7)),
            "car_class": random.choice(cls.CLASS_TYPES),
            "reg_number": f"IL-{uuid.uuid4().hex[:8].upper()}",
            "price": str(random.randint(100, 1000)),
            "about": fake.sentence(),
            "photo_path": None,
        }

        data.update(overrides)
        return Car(**data)
