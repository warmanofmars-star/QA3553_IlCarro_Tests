import pytest
import allure
from api.car_api import IlCarroAPI
from data.data_generator import CarGenerator, UserGenerator, SearchDataGenerator

pytestmark = [pytest.mark.api, pytest.mark.security]


@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Authentication (Tokens)")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.parametrize("token_strategy, expected_status, scenario", [
    ("empty", 403, "Пустой токен (Отсутствует заголовок)"),# <-- Ожидаем 403, так как Spring Boot по умолчанию так делает
    ("invalid", 401, "Невалидный токен (Мусорная строка)"),
    ("wrong_scheme", 401, "Неверная схема (Basic вместо Bearer)")
])
def test_api_security_auth_tokens(token_strategy, expected_status, scenario):
    """
    Проверка того, как сервер отбивает неавторизованные запросы
    с разными проблемами в заголовке Authorization.
    """
    api = IlCarroAPI()

    if token_strategy == "empty":
        # Ничего не добавляем, заголовка нет
        pass
    elif token_strategy == "invalid":
        api.session.headers.update({"Authorization": "Bearer fake_invalid_token_123"})
    elif token_strategy == "wrong_scheme":
        # Передаем валидный токен, но с неправильной схемой (Basic)
        # Для этого сначала зарегистрируем временного юзера
        temp_user = UserGenerator.get_random_user()
        res = api.register(temp_user.email, temp_user.password)
        valid_token = res.json().get("accessToken")
        # Принудительно меняем схему
        api.session.headers.update({"Authorization": f"Basic {valid_token}"})

    with allure.step(f"Сценарий: {scenario} -> Попытка запросить список машин"):
        response = api.get_my_cars()

    with allure.step(f"Проверка: Сервер должен вернуть {expected_status} Unauthorized"):
        assert response.status_code == expected_status, f"УЯЗВИМОСТЬ: Ожидался статус {expected_status}, получен {response.status_code}"


@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("BOLA (Broken Object Level Authorization)")
@allure.severity(allure.severity_level.BLOCKER)
def test_api_security_bola_delete():
    """
    Проверка на уязвимость BOLA (Insecure Direct Object References).
    Пользователь 'А' создает машину. Пользователь 'Б' пытается её удалить.
    """
    # 1. Создаем Пользователя 'А' и его машину
    user_a = UserGenerator.get_random_user()
    api_a = IlCarroAPI()
    api_a.register(user_a.email, user_a.password)

    car_a = CarGenerator.get_random_car()
    api_a.add_car(car_a.to_api_payload())
    serial_number_a = car_a.reg_number

    # 2. Создаем Пользователя 'Б'
    user_b = UserGenerator.get_random_user()
    api_b = IlCarroAPI()
    api_b.register(user_b.email, user_b.password)

    with allure.step("Уязвимость BOLA: Пользователь 'Б' пытается удалить машину Пользователя 'А'"):
        # Пользователь 'Б' делает DELETE-запрос по серийнику машины 'А'
        response = api_b.delete_car(serial_number_a)

    with allure.step("Проверка: Сервер должен запретить удаление чужой машины (403/400)"):
        # По стандартам безопасности сервер должен вернуть 403 Forbidden или 404 Not Found (чтобы скрыть существование объекта).
        # В IlCarro реализация может отличаться, поэтому мы проверяем, что статус ТОЧНО НЕ 200.
        assert response.status_code != 200, "КРИТИЧЕСКАЯ УЯЗВИМОСТЬ BOLA! Пользователь Б удалил машину Пользователя А!"

        # Если бэкенд возвращает 400 вместо 403/404, это тоже архитектурный недочет (bad practice),
        # но главное, что удаление заблокировано.
        assert response.status_code in [400, 403, 404], f"Ожидался статус запрета, получен {response.status_code}"

    # 3. Teardown: Убираем за собой (Пользователь 'А' удаляет свою машину)
    api_a.delete_car(serial_number_a)


@allure.epic("API Testing")
@allure.feature("Car Controller")
@allure.story("Idempotency (DELETE)")
@allure.severity(allure.severity_level.NORMAL)
def test_api_idempotency_delete(auth_api):
    """
    Проверка на идемпотентность DELETE-метода.
    Повторное удаление уже удаленного ресурса не должно валить сервер (500).
    """
    car = CarGenerator.get_random_car()
    serial_number = car.reg_number

    with allure.step("Пререквизит: Создаем машину"):
        auth_api.add_car(car.to_api_payload())

    with allure.step("Шаг 1: Удаляем машину (Первый запрос)"):
        res_first = auth_api.delete_car(serial_number)
        assert res_first.status_code == 200, "Первое удаление провалилось"

    with allure.step("Шаг 2: Удаляем ту же машину (Повторный запрос)"):
        res_second = auth_api.delete_car(serial_number)

    with allure.step("Проверка: Сервер корректно обработал дублирующий DELETE-запрос"):
        # По RFC идемпотентный DELETE может вернуть 200, 204 или 404.
        # В IlCarro мы ожидаем 400 Bad Request ("Car not found"), но сервер падает с 500.
        # Поэтому тест сразу размечен как xfail.
        assert res_second.status_code in [400, 404], f"Ожидалась корректная обработка отсутствующей машины, но сервер вернул {res_second.status_code}. Ответ: {res_second.text}"


@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("HTTP Methods Restrictions (405)")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.xfail(reason="BUG BACKEND: Spring Security возвращает 403 вместо 405 Method Not Allowed")
def test_api_security_method_not_allowed(auth_api):
    """
    Проверка 16 из статьи: Сервер должен блокировать неподдерживаемые HTTP-методы.
    Пытаемся обновить машину через неподдерживаемый метод PUT.
    """
    car = CarGenerator.get_random_car()

    with allure.step("Отправляем PUT-запрос вместо POST на эндпоинт создания машины"):
        # Вызываем .put напрямую через базовую сессию requests
        url = f"{auth_api.BASE_URL}/v1/cars"
        response = auth_api.session.put(url, json=car.to_api_payload())

    with allure.step("Проверка: Ожидаем 405 Method Not Allowed"):
        assert response.status_code == 405, f"БАГ БЭКЕНДА: Ожидался статус 405, получен {response.status_code}. Ответ: {response.text}"


@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Content-Type Validation (415)")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.xfail(reason="BUG BACKEND: 500 Internal Server Error при неверном Content-Type вместо 415")
def test_api_security_unsupported_media_type(auth_api):
    """
    Проверка 8 из статьи: Валидация заголовков.
    Сервер не должен пытаться парсить простой текст, если жестко ожидает JSON.
    """
    url = f"{auth_api.BASE_URL}/v1/cars"

    with allure.step("Отправляем обычный текст с заголовком text/plain вместо application/json"):
        headers = {"Content-Type": "text/plain"}
        response = auth_api.session.post(url, data="Just some malicious plain text here", headers=headers)

    with allure.step("Проверка: Ожидаем 415 Unsupported Media Type"):
        assert response.status_code == 415, f"БАГ БЭКЕНДА: Ожидался статус 415, получен {response.status_code}. Ответ: {response.text}"


@allure.epic("API Testing")
@allure.feature("Security")
@allure.story("Pagination DoS Protection")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.xfail(reason="BUG BACKEND / УЯЗВИМОСТЬ: Отсутствует хард-лимит пагинации. Возможна DoS-атака.")
def test_api_security_pagination_dos(auth_api):
    """
    Проверка 9 из статьи: Граничные значения.
    Тест на уязвимость отказа в обслуживании (DoS) через параметры пагинации.
    """
    target_city = "Tel Aviv"
    start_dt, end_dt = SearchDataGenerator.get_safe_future_dates()
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    with allure.step("Запрашиваем поиск машин с гигантским параметром size=1000000"):
        url = f"{auth_api.BASE_URL}/v1/cars/search?page=0&size=1000000"
        payload = {"city": target_city, "startDate": start_date, "endDate": end_date}
        response = auth_api.session.post(url, json=payload)

    with allure.step("Проверка: Сервер не упал с 500 и принудительно ограничил выдачу"):
        assert response.status_code != 500, "КРИТИЧЕСКАЯ УЯЗВИМОСТЬ: Сервер упал (500 Internal Server Error) от попытки достать миллион записей!"

        if response.status_code == 200:
            cars_returned = len(response.json().get("cars", []))
            # Здоровый бэкенд должен жестко лимитировать size (например, максимум 100-500 записей на страницу)
            assert cars_returned < 1000, f"УЯЗВИМОСТЬ ПАГИНАЦИИ: Сервер не имеет лимитов и попытался отдать слишком много данных ({cars_returned} машин)!"
