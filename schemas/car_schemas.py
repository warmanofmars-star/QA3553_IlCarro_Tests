# schemas/car_schemas.py

# Схема для дат бронирования (вложена внутри машины)
BOOKED_PERIOD_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string"},
        "startDate": {"type": "string"},
        "endDate": {"type": "string"}
    }
}

# Строгий контракт CarDto из Swagger
CAR_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "serialNumber": {"type": "string"},
        "manufacture": {"type": "string"},
        "model": {"type": "string"},
        "year": {"type": "string"},
        "fuel": {"type": "string"},
        "seats": {"type": "integer"},  # Swagger указывает четко: integer (int32)
        "carClass": {"type": "string"},
        "pricePerDay": {"type": "number"}, # Swagger: number (double)
        "about": {"type": "string"},
        "city": {"type": "string"},
        "lat": {"type": "number"}, # Координаты (могут вернуться, даже если не отправляли)
        "lng": {"type": "number"},
        "image": {"type": ["string", "null"]},
        "owner": {"type": "string"},
        "bookedPeriods": {
            "type": "array",
            "items": BOOKED_PERIOD_SCHEMA
        }
    },
    # Строго берем массив required из Swagger-документации:
    "required": [
        "carClass", "city", "fuel", "manufacture", "model",
        "pricePerDay", "seats", "serialNumber", "year"
    ]
}

# Схема ответа CarsDto
GET_CARS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "cars": {
            "type": "array",
            "items": CAR_OBJECT_SCHEMA
        }
    },
    # Мы не ставим "cars" в required жестко, так как при пустом списке может вернуться {}
    # в зависимости от реализации, но если массив есть, он должен быть валидным.
}