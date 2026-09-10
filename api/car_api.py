import requests
import os
import allure


class IlCarroAPI:
    BASE_URL = os.getenv("API_BASE_URL", "https://ilcarro-backend.herokuapp.com")

    def __init__(self):
        self.token = None

    def login(self, username, password):
        # Перенесли шаг внутрь. Переменную password нигде не выводим!
        with allure.step(f"API: Авторизация пользователя {username}"):
            url = f"{self.BASE_URL}/v1/user/login/usernamepassword"
            payload = {
                "username": username,
                "password": password
            }
            response = requests.post(url, json=payload)

            if response.status_code == 200:
                self.token = response.json().get("accessToken")

            return response

    @allure.step("API: Добавление новой машины")
    def add_car(self, car_payload):
        url = f"{self.BASE_URL}/v1/cars"

        # Сваггер требует передавать токен в заголовке Authorization (Bearer Authentication)
        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        response = requests.post(url, json=car_payload, headers=headers)
        return response

    @allure.step("API: Получение списка своих машин")
    def get_my_cars(self):
        url = f"{self.BASE_URL}/v1/cars/my"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        return requests.get(url, headers=headers)

    @allure.step("API: Удаление машины по серийному номеру {serial_number}")
    def delete_car(self, serial_number):
        url = f"{self.BASE_URL}/v1/cars/{serial_number}"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        return requests.delete(url, headers=headers)

    @allure.step("API: Поиск машин в городе {city}")
    def search_cars(self, city, start_date, end_date):
        url = f"{self.BASE_URL}/v1/cars/search"
        payload = {
            "city": city,
            "startDate": start_date,
            "endDate": end_date
        }
        # Поиск доступен без авторизации, поэтому headers не передаем
        return requests.post(url, json=payload)

    @allure.step("API: Бронирование машины {serial_number}")
    def book_car(self, serial_number, start_date, end_date):
        url = f"{self.BASE_URL}/v1/cars/{serial_number}/booking"
        payload = {
            "startDate": start_date,
            "endDate": end_date
        }
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        return requests.post(url, json=payload, headers=headers)