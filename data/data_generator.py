import random
import string
from faker import Faker
from models.user import User

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