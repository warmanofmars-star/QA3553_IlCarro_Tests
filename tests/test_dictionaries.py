import allure
import pytest
from api.car_api import IlCarroAPI

FRONTEND_CITIES = [
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


@allure.epic("Data Integrity")
@allure.feature("Cross-System Dictionaries")
@allure.title("Строгое соответствие словаря городов (Frontend vs Backend)")
@pytest.mark.xfail(reason="Глобальный рассинхрон: Фронтенд использует захардкоженный список городов, отличный от БД")
def test_frontend_backend_cities_mapping():
    api = IlCarroAPI()

    with allure.step("1. Получаем словарь бэкенда"):
        response = api.get_cities()
        assert response.status_code == 200, "API недоступно"
        backend_cities = [city["city"] for city in response.json().get("cities", [])]

    with allure.step("2. Нормализация и сравнение списков"):
        front_set = set(FRONTEND_CITIES)
        back_set = set(backend_cities)

        fake_frontend_cities = front_set - back_set
        unreachable_backend_cities = back_set - front_set

        error_msg = ""
        if fake_frontend_cities:
            error_msg += f"\n[CRITICAL] Фронтенд отправляет города, которых нет в БД: {sorted(fake_frontend_cities)}"
        if unreachable_backend_cities:
            error_msg += f"\n[WARNING] В БД есть машины в этих городах, но юзер их не найдет: {sorted(unreachable_backend_cities)}"

        assert not fake_frontend_cities and not unreachable_backend_cities, error_msg