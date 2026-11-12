"""
Даты поиска и бронирования, которые не имеют смысла: наблюдение OBS-02.

Ожидание — запрос отклоняется (4xx): прошедшие даты и конец раньше начала не описывают никакого
реального периода аренды (логика предметной области). Swagger ограничений на даты не задаёт, поэтому
это наблюдение, а не требование. Факты: Q-API-01, Q-API-02, Q-API-18 — везде 200.

Случай «без дат» не проверяется: в Swagger у SearchDto и BookingPeriodDto нет обязательных полей,
контракт сам разрешает запрос без дат.

Бронируется своя машина общего пользователя, созданная фабрикой и удаляемая после теста: если
бронирование когда-нибудь начнёт сохраняться, бессмысленные даты не попадут в чужие машины.
Поиск — только по малому городу (ответ по крупному весит десятки мегабайт, Q-API-02).
"""

from datetime import date, timedelta

import allure
import pytest

from data.data_generator import SearchDataGenerator
from data.observations import observation

pytestmark = [pytest.mark.api, pytest.mark.regression]


def _dates(case: str) -> tuple[str, str]:
    today = date.today()
    if case == "past_dates":
        start, end = today - timedelta(days=10), today - timedelta(days=6)
    else:  # end_before_start
        start, end = today + timedelta(days=25), today + timedelta(days=20)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


@allure.epic("API Testing")
@allure.feature("Search and Booking")
@allure.story("Meaningless dates")
@allure.title("Поиск и бронирование с бессмысленными датами отклоняются")
@observation("INVALID_DATES_ACCEPTED")
@allure.tag("OBS-02")
@pytest.mark.parametrize("operation", ["search", "booking"])
@pytest.mark.parametrize("dates_case", ["past_dates", "end_before_start"])
def test_api_meaningless_dates_rejected(shared_api, shared_create_car, operation, dates_case):
    start, end = _dates(dates_case)
    city = SearchDataGenerator.SMALL_CITY
    allure.dynamic.parameter("Период", f"{start} — {end}")

    if operation == "search":
        response = shared_api.search_cars(city, start, end)
    else:
        car = shared_create_car(city=city)
        response = shared_api.book_car(car.reg_number, start, end)

    with allure.step(f"Проверка: {operation} с периодом {start} — {end} отклонён (4xx)"):
        assert 400 <= response.status_code < 500, (
            f"{operation} с периодом {start} — {end} принят: {response.status_code} {response.text[:200]}"
        )
