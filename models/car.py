from dataclasses import dataclass

@dataclass
class Car:
    city: str
    make: str
    model: str
    year: str
    fuel: str
    gear: str
    wd: str
    doors: str
    seats: str
    car_class: str
    reg_number: str
    price: str
    about: str
    photo_path: str = None

    def to_api_payload(self) -> dict:
        """
        Превращает объект Car в словарь формата JSON для отправки на API.
        Автоматически маппит python-свойства в нужные API-ключи и приводит типы.
        """
        return {
            "serialNumber": self.reg_number,
            "manufacture": self.make,
            "model": self.model,
            "year": str(self.year),
            "fuel": self.fuel,
            "seats": int(self.seats),
            "carClass": self.car_class,
            "pricePerDay": float(self.price),
            "about": self.about,
            "city": self.city
        }