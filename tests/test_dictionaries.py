import allure
import pytest

from api.car_api import IlCarroAPI
from data.known_bugs import known_bug
from utils.preconditions import require

pytestmark = [pytest.mark.api, pytest.mark.regression, pytest.mark.contract]

FRONTEND_CITIES = [
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


@allure.epic("Data Integrity")
@allure.feature("Cross-System Dictionaries")
@allure.title("Строгое соответствие словаря городов (Frontend vs Backend)")
@known_bug("CITIES_MISMATCH")
@allure.tag("DISC-02")
def test_frontend_backend_cities_mapping():
    api = IlCarroAPI()

    with allure.step("1. Получаем словарь бэкенда"):
        response = api.get_cities()
        require(response.status_code == 200, "API недоступно")
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
            error_msg += (
                "\n[WARNING] В БД есть машины в этих городах, но юзер их не найдет: "
                f"{sorted(unreachable_backend_cities)}"
            )

        assert not fake_frontend_cities, error_msg
        assert not unreachable_backend_cities, error_msg


def _is_number(value) -> bool:
    # bool в Python — подкласс int, но координатой не является
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_city_item(item) -> bool:
    """Элемент CitiesDto: непустое название города и координаты-числа."""
    return (
        isinstance(item, dict)
        and isinstance(item.get("city"), str)
        and bool(item["city"])
        and _is_number(item.get("lat"))
        and _is_number(item.get("lng"))
    )


@allure.epic("API Testing")
@allure.feature("Cross-System Dictionaries")
@allure.title("Список городов API доступен без авторизации и состоит из {city, lat, lng}")
@allure.tag("REQ-CITY-01")
def test_api_cities_list():
    api = IlCarroAPI()  # клиент без заголовка Authorization

    response = api.get_cities()

    with allure.step("Проверка: без токена — 200"):
        assert response.status_code == 200, f"Список городов без токена: {response.status_code} {response.text}"

    with allure.step("Проверка: непустой список элементов {city, lat, lng}"):
        cities = response.json().get("cities")
        assert isinstance(cities, list), f"В ответе нет списка cities: {response.text[:500]}"
        assert cities, "Список городов пуст"
        broken = [item for item in cities if not _is_city_item(item)]
        assert not broken, f"Элементы не в формате {{city: строка, lat: число, lng: число}}: {broken[:5]}"
