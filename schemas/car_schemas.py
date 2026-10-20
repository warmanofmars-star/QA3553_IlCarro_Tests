# Схема для дат бронирования
BOOKED_PERIOD_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {"type": "string"},
        "startDate": {"type": "string"},
        "endDate": {"type": "string"}
    },
    "required": ["email", "startDate", "endDate"],
    "additionalProperties": False  # 🔥 Запрещаем любые лишние поля от бэкенда!
}

# Строгий контракт CarDto
CAR_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "serialNumber": {"type": "string"},
        "manufacture": {"type": "string"},
        "model": {"type": "string"},
        "year": {"type": "string"},
        "fuel": {"type": "string"},
        "seats": {"type": "integer"},
        "carClass": {"type": "string"},
        "pricePerDay": {"type": "number"},
        "about": {"type": "string"},
        "city": {"type": "string"},
        "lat": {"type": "number"},
        "lng": {"type": "number"},
        "image": {"type": ["string", "null"]},
        "owner": {"type": "string"},
        "bookedPeriods": {
            "type": "array",
            "items": BOOKED_PERIOD_SCHEMA
        }
    },
    "required": [
        "carClass", "city", "fuel", "manufacture", "model",
        "pricePerDay", "seats", "serialNumber", "year"
    ],
    "additionalProperties": False  # 🔥 Строгий контроль контракта
}

# Схема ответа GET /v1/cars/my
GET_CARS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "cars": {
            "type": "array",
            "items": CAR_OBJECT_SCHEMA
        }
    },
    "required": ["cars"],
    "additionalProperties": False
}

# Схема для POST и DELETE (когда возвращается просто {"message": "..."})
MESSAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"}
    },
    "required": ["message"],
    "additionalProperties": False
}