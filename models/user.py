from dataclasses import dataclass


@dataclass
class User:
    name: str
    last_name: str
    email: str
    password: str

    def to_api_payload(self) -> dict:
        """Превращает объект User в словарь формата JSON для регистрации через API."""
        return {
            "firstName": self.name,
            "lastName": self.last_name,
            "username": self.email,
            "password": self.password
        }