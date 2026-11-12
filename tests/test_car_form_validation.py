"""
Проверка формы добавления машины до отправки: REQ-UI-CAR-01 и сторона фронтенда расхождения DISC-07.

Форма не отправляется: кнопку Submit тесты не нажимают, запросов к API, меняющих данные, нет.
Каждый тест начинает с целиком заполненной допустимыми значениями формы (кнопка Submit доступна —
контроль, что форма сама по себе валидна), затем портит одно поле и снимает с него фокус.

Пользователь — общий (shared_user), вход токеном в localStorage: меняется только состояние браузера.
Тексты ошибок — из кода фронтенда (LetCarWork: schema с required("Required")) и подтверждены Q-UI-20.
"""

import allure
import pytest

from data.data_generator import CarGenerator
from data.known_bugs import known_bug
from pages.add_car_page import AddCarPage
from pages.login_page import LoginPage
from utils.preconditions import require

pytestmark = [pytest.mark.ui, pytest.mark.regression]

# Текст ошибки обязательного поля — из схемы валидации формы (FE: LetCarWork)
REQUIRED_ERROR = "Required"


@pytest.fixture
def car_form(shared_authenticated_driver) -> AddCarPage:
    """Форма машины залогиненного пользователя, заполненная допустимыми значениями; Submit доступна."""
    add_car_page = AddCarPage(shared_authenticated_driver)
    add_car_page.open()
    require(LoginPage(shared_authenticated_driver).is_logout_button_visible(), "Предусловие: вход токеном не сработал")
    add_car_page.fill_valid_form(CarGenerator.get_random_car())
    # Контроль: без порчи форма валидна. Иначе недоступная кнопка ничего не говорила бы о проверяемом поле
    require(add_car_page.wait_submit_enabled(), "Предусловие: заполненная форма не валидна — Submit недоступна")
    return add_car_page


@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Form validation before submit")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("REQ-UI-CAR-01")
@pytest.mark.parametrize(
    "field_name, label",
    [
        ("manufacture", "Make"),
        ("model", "Model"),
        ("year", "Year"),
        ("fuel", "Fuel"),
        ("seats", "Seats"),
        ("carClass", "Car class"),
        ("serialNumber", "Car registration number"),
        ("pricePerDay", "Price"),
    ],
)
def test_car_form_required_field(car_form, field_name, label):
    with allure.step(f"Поле «{label}» опустошено, фокус снят"):
        if field_name == "fuel":
            car_form.clear_fuel()
        else:
            car_form.replace_value(car_form.field(field_name), "")
        car_form.blur()

    with allure.step(f"Проверка: под «{label}» ошибка «{REQUIRED_ERROR}», Submit недоступна"):
        error = car_form.get_field_error_text(field_name)
        assert error == REQUIRED_ERROR, f"Под пустым полем «{label}» ожидали «{REQUIRED_ERROR}», получили {error!r}"
        assert car_form.wait_submit_disabled(), f"С пустым полем «{label}» кнопка Submit осталась доступной"


@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Form validation before submit")
@allure.severity(allure.severity_level.NORMAL)
@known_bug("CAR_FORM_CITY_NOT_VALIDATED")
@allure.tag("REQ-UI-CAR-01")
def test_car_form_city_required(car_form):
    """City отмечен «*», но в схеме валидации его нет: с пустым городом форма уходит на сервер (Q-UI-04, Q-UI-20)."""
    with allure.step("Город, выбранный из подсказки, стёрт; фокус снят"):
        car_form.replace_value(car_form.CITY_INPUT, "")
        car_form.blur()
        value = car_form.find(car_form.CITY_INPUT).get_attribute("value")
        require(value == "", f"Предусловие: поле City не опустело, в нём {value!r}")

    with allure.step("Проверка: с пустым City кнопка Submit недоступна"):
        assert car_form.wait_submit_disabled(), "С пустым полем City кнопка Submit осталась доступной"


@allure.epic("UI Testing")
@allure.feature("Add Car Page (Let the car work)")
@allure.story("Form validation before submit")
@allure.severity(allure.severity_level.NORMAL)
@allure.tag("DISC-07")
@pytest.mark.parametrize(
    "field_name, label, value",
    [
        ("seats", "Seats", "0"),
        ("seats", "Seats", "-1"),
        ("pricePerDay", "Price", "0"),
        ("pricePerDay", "Price", "-5"),
    ],
)
def test_car_form_value_below_one(car_form, field_name, label, value):
    """Фронт требует Seats ≥ 1 и Price ≥ 1 — сторона фронта расхождения DISC-07. Что API те же значения
    принимает, проверяет test_api_rejects_car_values_forbidden_by_form (известный баг CAR_LIMITS_MISMATCH).

    Текст ошибки не сверяется: это сообщение по умолчанию библиотеки валидации, а не текст приложения.
    """
    with allure.step(f"В поле «{label}» введено {value}, фокус снят"):
        car_form.replace_value(car_form.field(field_name), value)
        car_form.blur()

    with allure.step(f"Проверка: под «{label}» есть ошибка, Submit недоступна"):
        error = car_form.get_field_error_text(field_name)
        assert error, f"Под полем «{label}» со значением {value} нет ошибки валидации"
        assert car_form.wait_submit_disabled(), f"Со значением «{label}» = {value} кнопка Submit осталась доступной"
