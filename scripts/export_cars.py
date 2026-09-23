import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (если он есть)
load_dotenv()

# Берем ссылку из окружения, оставляя надежный фоллбэк
BASE_URL = os.getenv("API_BASE_URL", "https://ilcarro-backend.herokuapp.com")


def export_all_available_cars():
    print(f"🌍 1. Запрашиваем список городов с сервера: {BASE_URL}")
    cities_resp = requests.get(f"{BASE_URL}/v1/cars/cities")

    if cities_resp.status_code != 200:
        print(f"❌ Ошибка получения городов: {cities_resp.status_code}")
        return

    cities = [c["city"] for c in cities_resp.json().get("cities", [])]
    print(f"✅ Найдено городов: {len(cities)}")

    # Берем широкий диапазон: с завтрашнего дня и на 30 дней вперед
    start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    all_cars = []

    print(f"🚗 2. Начинаем сбор машин (Даты: {start_date} - {end_date})...")
    for city in cities:
        payload = {
            "city": city,
            "startDate": start_date,
            "endDate": end_date
        }

        search_resp = requests.post(f"{BASE_URL}/v1/cars/search", json=payload)

        if search_resp.status_code == 200:
            found_cars = search_resp.json().get("cars", [])
            all_cars.extend(found_cars)
            print(f"  📍 {city}: найдено {len(found_cars)} машин")
        else:
            print(f"  ⚠️ {city}: ошибка поиска ({search_resp.status_code})")

    # 3. Очистка от дубликатов
    unique_cars = {car["serialNumber"]: car for car in all_cars}.values()

    # 4. Сохранение в JSON
    filepath = "full_cars_database.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(list(unique_cars), f, indent=4, ensure_ascii=False)

    print(f"\n🎉 Готово! Успешно выгружено {len(unique_cars)} уникальных машин в файл {filepath}")


if __name__ == "__main__":
    export_all_available_cars()