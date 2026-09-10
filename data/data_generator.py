import random
import string
from datetime import datetime, timedelta
from faker import Faker
from models.user import User
from models.car import Car

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


class SearchDataGenerator:
    # Полный фиксированный список городов из выпадающего списка IlCarro
    CITIES = [
        "Tel Aviv",
        "Jerusalem",
        "Haifa",
        "Rishon LeZion",
        "Petah Tikva",
        "Ashdod",
        "Netanya",
        "Beersheba"
    ]

    @classmethod
    def get_random_city(cls):
        return random.choice(cls.CITIES)

    @staticmethod
    def get_safe_future_dates(min_offset=1, max_offset=10, min_duration=2, max_duration=6):
        """
        Генерирует даты в будущем.
        :param min_offset: Минимальное количество дней от сегодня до начала аренды
        :param max_offset: Максимальное количество дней до начала аренды
        :param min_duration: Минимальная длительность поездки
        :param max_duration: Максимальная длительность поездки
        """
        today = datetime.now()

        # Настраиваемое смещение до начала поездки
        start_offset = random.randint(min_offset, max_offset)
        start_date = today + timedelta(days=start_offset)

        # Настраиваемая длительность
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

    @classmethod
    def get_random_car(cls, photo_path=None, **overrides):
        data = {
            "city": SearchDataGenerator.get_random_city(),
            "make": random.choice(cls.MAKE_TYPES),
            "model": random.choice(cls.MODEL_TYPES),
            "year": str(random.randint(2010, 2024)),
            "fuel": random.choice(cls.FUEL_TYPES),
            "gear": random.choice(cls.GEAR_TYPES),
            "wd": random.choice(cls.WD_TYPES),
            "doors": str(random.randint(2, 5)),
            "seats": str(random.randint(2, 7)),
            "car_class": random.choice(cls.CLASS_TYPES),
            "reg_number": f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(100, 999)}",
            "price": str(random.randint(50, 500)),
            "about": "",  # Оставляем пустым, чтобы обойти возможный баг бэкенда
            "photo_path": photo_path
        }
        data.update(overrides)
        from models.car import Car
        return Car(**data)