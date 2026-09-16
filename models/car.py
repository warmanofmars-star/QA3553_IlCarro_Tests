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
    # Важное правило Python: поля со значением по умолчанию всегда идут в самом конце!
    photo_path: str = None