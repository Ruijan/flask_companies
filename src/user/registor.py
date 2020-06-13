from abc import abstractmethod
from datetime import datetime

from src.brokers.degiro import Degiro
from src.user.degiro_user import DegiroUser
from src.user.user import User


class Registrator:
    def __init__(self, encryptor, user_collection):
        self.encryptor = encryptor
        self.collection = user_collection

    @abstractmethod
    def register(self, data, locator):
        pass


class EmailRegistrator(Registrator):
    def register(self, data, locator):
        now = datetime.now()
        data = {"pass": self.encryptor.encrypt(data["password"].encode()),
                "first_name": self.encryptor.encrypt(data["first_name"].encode()),
                "last_name": self.encryptor.encrypt(data["last_name"].encode()),
                "email": data["email"],
                "type": "email",
                "creation_date": now,
                "last_connection": now,
                "geolocation": locator.get_geoip_data()}
        user = self.collection.find_one({"email": data["email"]})
        if user is not None:
            raise RegistrationException("Email already in database. Try signing in.")
        user_id = self.collection.insert_one(data)
        return User(user_id.inserted_id, data["first_name"], data["last_name"], data["email"], now, now,
                    data["geolocation"],
                    self.encryptor)


class DegiroRegistrator(Registrator):
    def register(self, data, locator):
        degiro = Degiro()
        try:
            degiro.login(data["username"], data["password"], data["code"] if len(data["code"]) > 0 else None)
        except ConnectionError as err:
            raise RegistrationException(err)
        now = datetime.now()
        user = DegiroUser(None, degiro.user["firstContact"]["firstName"],
                          degiro.user["firstContact"]["lastName"],
                          degiro.user["email"], now, now, locator.get_geoip_data(), self.encryptor,
                          degiro.session_id,
                          degiro.account_id)
        if User.does_email_exist(self.collection, user.email):
            raise RegistrationException("Email already in database. Try signing in.")
        user.id = self.collection.insert_one(user.to_db_dict()).inserted_id
        return user


class RegistratorFactory:
    @staticmethod
    def create(registration_method, encryptor, user_collection):
        if registration_method == "email":
            return EmailRegistrator(encryptor, user_collection)
        elif registration_method == "degiro":
            return DegiroRegistrator(encryptor, user_collection)
        else:
            raise AttributeError("Registration method " + registration_method + " does not exist.")


class RegistrationException(Exception):
    def __init__(self, message):
        self.message = message
