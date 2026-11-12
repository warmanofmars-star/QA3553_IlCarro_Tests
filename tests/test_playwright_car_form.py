"""
Что форма добавления машины отправляет в API: REQ-UI-CAR-03, REQ-UI-CAR-04 и расхождение DISC-04.

Запрос POST /v1/cars перехватывается и получает подменённый ответ 200 в формате настоящего
({"message": "Car added successfully"}, Q-UI-05). До бэкенда он не доходит: машин тесты не создают,
фото на общем сервере не копят (REQ-SEC-07). Запрос мимо подмены (опечатка в шаблоне) обрывает
защита backend_write_guard: до бэкенда он тоже не доходит. Подменённый ответ нужен только затем,
чтобы прочитать отправленное; что фронт показывает после ответа, проверяет только тест текста
успешной отправки (REQ-UI-CAR-02).

Пользователь — общий (shared_user): меняется только состояние браузера, ответы подменены. Вход —
токеном в localStorage, без запроса входа к бэкенду.
"""

import base64

import allure
import pytest
from playwright.sync_api import Page, expect

from config import PROJECT_ROOT
from data.data_generator import CarGenerator
from data.known_bugs import known_bug
from models.car import Car
from pages.pw_add_car_page import PwAddCarPage
from pages.pw_login_page import PwLoginPage
from utils.network_faults import CAR_ADDED, CARS, NetworkFaults, require_intercepted, send_and_settle
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]

PHOTO_FILE = PROJECT_ROOT / "assets" / "car.jpg"
PHOTO_LINK = "https://example.com/test-car.jpg"


@pytest.fixture
def car_form(page: Page, shared_user, backend_write_guard) -> PwAddCarPage:
    """Форма добавления машины, открытая залогиненным общим пользователем; записи мимо подмен обрываются."""
    add_car_page = PwAddCarPage(page)
    add_car_page.restore_session(shared_user.api.token)
    add_car_page.open()
    # wait_for, а не expect: вход — предусловие и для теста под known_bug
    PwLoginPage(page).logout_btn.wait_for(state="visible")
    return add_car_page


def _submit_and_read_request(page: Page, add_car_page: PwAddCarPage, cleanup, car: Car) -> dict:
    """Отправляет заполненную форму и возвращает тело перехваченного запроса POST /v1/cars."""
    # Страховка: если перехват не сработает и машина всё-таки создастся на бэкенде, очистка её удалит
    cleanup.register(car.reg_number)
    sent = NetworkFaults(page).respond(CARS, "POST", 200, CAR_ADDED)

    with allure.step("Отправка формы: POST /v1/cars перехвачен, ответ подменён на 200"):
        send_and_settle(page, "POST", "/v1/cars", add_car_page.submit)
        # Главное предусловие: без пойманного запроса проверка его содержимого пуста
        require_intercepted(sent, "POST /v1/cars")

    body = sent[0].post_data_json
    require(isinstance(body, dict), f"Тело перехваченного запроса — не JSON-объект: {type(body).__name__}")
    # Запрос тот самый: отправлена машина, которую заполнил тест
    require(
        body.get("serialNumber") == car.reg_number,
        f"Перехвачен запрос с другой машиной: serialNumber={body.get('serialNumber')!r}, ждали {car.reg_number!r}",
    )
    return body


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("What the car form sends")
@allure.title("Fuel уходит в API строчными")
@allure.tag("REQ-UI-CAR-03")
@pytest.mark.parametrize(
    "fuel_option, expected_fuel",
    [("Petrol", "petrol"), ("Diesel", "diesel"), ("Hybrid", "hybrid"), ("Electric", "electric")],
)
def test_pw_car_form_sends_fuel_lowercase(page: Page, car_form, shared_car_cleanup, fuel_option, expected_fuel):
    car = CarGenerator.get_random_car(fuel=fuel_option)

    with allure.step(f"Заполнение формы, в списке Fuel выбран вариант «{fuel_option}»"):
        car_form.fill_form(car)

    body = _submit_and_read_request(page, car_form, shared_car_cleanup, car)

    with allure.step(f"Проверка: fuel в запросе — «{expected_fuel}»"):
        assert body.get("fuel") == expected_fuel, (
            f"Для варианта «{fuel_option}» в запросе ожидали fuel={expected_fuel!r}, ушло {body.get('fuel')!r}"
        )


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("What the car form sends")
@allure.title("Фото файлом уходит в поле image как data URL")
@allure.tag("REQ-UI-CAR-04")
def test_pw_car_form_sends_photo_file_as_data_url(page: Page, car_form, shared_car_cleanup):
    car = CarGenerator.get_random_car()
    photo_bytes = PHOTO_FILE.read_bytes()

    with allure.step("Заполнение формы и выбор файла фото"):
        car_form.fill_form(car)
        car_form.attach_photo(str(PHOTO_FILE))

    body = _submit_and_read_request(page, car_form, shared_car_cleanup, car)

    with allure.step("Проверка: image — data URL с содержимым файла в base64"):
        # Значение длиной в сотни килобайт в сообщение не выводим: только начало и длину
        image = body.get("image") or ""
        prefix, separator, encoded = image.partition(",")
        assert (prefix, separator) == ("data:image/jpeg;base64", ","), (
            f"Поле image — не data URL JPEG в base64: начало {image[:40]!r}, длина {len(image)}"
        )
        assert encoded == base64.b64encode(photo_bytes).decode("ascii"), (
            f"Данные в image не совпадают с файлом: в запросе {len(encoded)} символов base64, "
            f"в файле {len(photo_bytes)} байт"
        )


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("What the car form sends")
@allure.title("Фото ссылкой уходит в поле image как введено")
@allure.tag("REQ-UI-CAR-04")
def test_pw_car_form_sends_photo_link(page: Page, car_form, shared_car_cleanup):
    car = CarGenerator.get_random_car()

    with allure.step("Заполнение формы, фото — ссылкой"):
        car_form.fill_form(car)
        car_form.fill_photo_link(PHOTO_LINK)

    body = _submit_and_read_request(page, car_form, shared_car_cleanup, car)

    with allure.step("Проверка: image в запросе — введённая ссылка"):
        assert body.get("image") == PHOTO_LINK, f"В запросе ожидали image={PHOTO_LINK!r}, ушло {body.get('image')!r}"


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("What the car form sends")
@allure.title("Gear, WD и Doors из формы попадают в запрос")
@known_bug("CAR_FORM_FIELDS_NOT_SENT")
@allure.tag("DISC-04")
def test_pw_car_form_sends_gear_wd_doors(page: Page, car_form, shared_car_cleanup):
    """
    Форма предлагает пользователю Gear, WD и Doors, а в CarDto таких полей нет (DISC-04): введённое
    молча теряется (Q-UI-05, Q-UI-15). Ожидание — введённое в форму доходит до запроса.
    """
    car = CarGenerator.get_random_car()

    with allure.step("Заполнение формы вместе с Gear, WD и Doors"):
        car_form.fill_form(car)
        entered = {
            "gear": car_form.gear_select.input_value(),
            "wheelsDrive": car_form.wd_select.input_value(),
            "doors": car_form.doors_input.input_value(),
        }
        # Без введённых значений вывод «поля потеряны» был бы пустым: терять было бы нечего
        require(all(entered.values()), f"Предусловие: Gear, WD и Doors в форме не заполнены: {entered}")

    body = _submit_and_read_request(page, car_form, shared_car_cleanup, car)

    with allure.step("Проверка: введённые Gear, WD и Doors есть в запросе"):
        lost = sorted(name for name in entered if name not in body)
        assert not lost, (
            f"Введённые в форму значения не попали в запрос POST /v1/cars: {lost} (в форме: {entered}; "
            f"ключи запроса: {sorted(body)})"
        )


@allure.epic("Playwright Testing")
@allure.feature("Cars Management")
@allure.story("Submit result")
@allure.title("После успешной отправки — «Car submitted successfully»")
@known_bug("CAR_SUCCESS_TEXT_NOT_SHOWN")
@allure.tag("REQ-UI-CAR-02")
def test_pw_car_form_success_text(page: Page, car_form, shared_car_cleanup):
    """
    Ответ 200 подменён в формате настоящего (Q-UI-05). Форма очищается — это проверяют тесты
    test_add_car_success; текста успеха на экране нет (Q-UI-15, Q-UI-26).
    """
    car = CarGenerator.get_random_car()
    car_form.fill_form(car)
    _submit_and_read_request(page, car_form, shared_car_cleanup, car)

    # Ответ обработан: форма очистилась. wait_for_function, а не expect — под xfail только проверка текста
    page.wait_for_function("() => document.querySelector(\"[name='manufacture']\").value === ''")

    with allure.step("Проверка: на экране «Car submitted successfully»"):
        expect(page.get_by_role("status"), "После успешной отправки нет текста успеха").to_have_text(
            "Car submitted successfully"
        )
