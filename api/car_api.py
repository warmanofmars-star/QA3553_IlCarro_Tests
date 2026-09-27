import os
import requests
import allure
from utils.logger import get_logger

logger = get_logger("API")


class IlCarroAPI:
    BASE_URL = os.getenv("API_BASE_URL", "https://ilcarro-backend.herokuapp.com")

    def __init__(self):
        # 1. Открываем единую сессию при создании клиента
        self.session = requests.Session()
        self.token = None

    def login(self, username, password):
        with allure.step(f"API: Авторизация пользователя {username}"):
            url = f"{self.BASE_URL}/v1/user/login/usernamepassword"
            logger.info(f"POST {url} [User: {username}]")

            payload = {
                "username": username,
                "password": password
            }
            # 2. Запрос делаем через сессию
            response = self.session.post(url, json=payload)

            if response.status_code == 200:
                self.token = response.json().get("accessToken")
                # 3. МАГИЯ: Один раз кладем токен в заголовки сессии,
                # и он автоматически будет прикрепляться ко всем будущим запросам!
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                logger.info("Авторизация успешна (Token получен и вшит в сессию)")
            else:
                logger.error(f"Ошибка авторизации: {response.status_code} - {response.text}")
            return response

    @allure.step("API: Добавление новой машины")
    def add_car(self, car_payload):
        url = f"{self.BASE_URL}/v1/cars"
        serial = car_payload.get('serialNumber', 'UNKNOWN')
        logger.info(f"POST {url} [Создание машины: {serial}]")

        # 4. Обрати внимание: параметра headers больше нет, код стал чище
        response = self.session.post(url, json=car_payload)

        if response.status_code == 200:
            logger.info(f"Машина {serial} успешно создана в БД")
        else:
            logger.error(f"Ошибка создания машины {serial}: {response.status_code} - {response.text}")

        return response

    @allure.step("API: Получение списка своих машин")
    def get_my_cars(self):
        url = f"{self.BASE_URL}/v1/cars/my"
        logger.info(f"GET {url} [Запрос списка своих машин]")

        response = self.session.get(url)

        if response.status_code != 200:
            logger.error(f"Ошибка получения списка машин: {response.status_code} - {response.text}")

        return response

    @allure.step("API: Удаление машины по серийному номеру {serial_number}")
    def delete_car(self, serial_number):
        url = f"{self.BASE_URL}/v1/cars/{serial_number}"
        logger.info(f"DELETE {url} [Удаление машины: {serial_number}]")

        response = self.session.delete(url)

        if response.status_code == 200:
            logger.info(f"Машина {serial_number} успешно удалена")
        else:
            logger.error(f"Ошибка удаления машины {serial_number}: {response.status_code} - {response.text}")

        return response

    @allure.step("API: Поиск машин в городе {city}")
    def search_cars(self, city, start_date, end_date):
        url = f"{self.BASE_URL}/v1/cars/search"
        logger.info(f"POST {url} [Поиск: {city}, даты: {start_date} - {end_date}]")

        payload = {
            "city": city,
            "startDate": start_date,
            "endDate": end_date
        }
        response = self.session.post(url, json=payload)

        if response.status_code == 200:
            cars_count = len(response.json().get("cars", []))
            logger.info(f"Поиск успешен. Найдено машин: {cars_count}")
        else:
            logger.error(f"Ошибка поиска в городе {city}: {response.status_code} - {response.text}")

        return response

    @allure.step("API: Бронирование машины {serial_number}")
    def book_car(self, serial_number, start_date, end_date):
        url = f"{self.BASE_URL}/v1/cars/{serial_number}/booking"
        logger.info(f"POST {url} [Бронирование: {serial_number}, даты: {start_date} - {end_date}]")

        payload = {
            "startDate": start_date,
            "endDate": end_date
        }
        response = self.session.post(url, json=payload)

        if response.status_code == 200:
            logger.info(f"Машина {serial_number} успешно забронирована")
        else:
            logger.error(f"Ошибка бронирования машины {serial_number}: {response.status_code} - {response.text}")

        return response

    @allure.step("API: Получение списка доступных городов")
    def get_cities(self):
        url = f"{self.BASE_URL}/v1/cars/cities"
        logger.info(f"GET {url} [Запрос списка городов]")

        response = self.session.get(url)

        if response.status_code != 200:
            logger.error(f"Ошибка получения списка городов: {response.status_code} - {response.text}")

        return response