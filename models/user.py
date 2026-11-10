from dataclasses import dataclass, field


@dataclass
class User:
    name: str
    last_name: str
    email: str
    # repr=False: pytest печатает repr аргументов теста в трассе упавшего (и xfail) теста, трасса
    # попадает в отчёт Allure — без этого пароль временного аккаунта оказывался в statusDetails.trace
    password: str = field(repr=False)

    def to_api_payload(self) -> dict:
        """Превращает объект User в словарь формата JSON для регистрации через API."""
        return {"firstName": self.name, "lastName": self.last_name, "username": self.email, "password": self.password}
