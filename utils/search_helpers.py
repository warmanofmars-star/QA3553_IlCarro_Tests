"""
Общая подготовка UI-тестов поиска, которые ищут в выдаче СВОЮ машину.

Пагинация выдачи клиентская: page и size передаются в URL (REQ-UI-SEARCH-04). Чтобы найти нашу
карточку, вся выдача города должна поместиться на одну страницу, поэтому тесты берут город с малым
числом машин (SearchDataGenerator.SMALL_CITY) и наибольший вариант size.
"""

from data.data_generator import SearchDataGenerator
from utils.preconditions import require

# 50 — наибольший вариант пагинации в коде фронтенда (REQ-UI-SEARCH-04)
RESULTS_PAGE_SIZE = 50


def require_city_fits_one_page(api, city, start_date, end_date) -> None:
    """Предусловие: город пригоден для UI и API, а его выдача помещается на одну страницу."""
    require(
        city in SearchDataGenerator.get_safe_cities(),
        f"Город {city} больше не входит в пересечение городов фронтенда и API",
    )
    response = api.search_cars(city, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    require(response.status_code == 200, f"Поиск через API недоступен: {response.status_code} {response.text}")
    total = len(response.json().get("cars", []))
    require(
        total <= RESULTS_PAGE_SIZE,
        f"В городе {city} уже {total} машин — больше {RESULTS_PAGE_SIZE}: нужен другой город с малым числом машин",
    )
