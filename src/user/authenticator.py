from abc import abstractmethod

from src.brokers.degiro import Degiro
from src.user.degiro_user import DegiroUser
from src.user.user import User


class Authenticator:
    def __init__(self, encryptor, user_collection):
        self.encryptor = encryptor
        self.collection = user_collection

    @abstractmethod
    def authenticate(self, data):
        pass


class EmailAuthenticator(Authenticator):
    def __init__(self, encryptor, user_collection):
        super().__init__(encryptor, user_collection)

    def authenticate(self, data):
        user = self.collection.find_one({"email": data["email"], "type": "email"})
        if user is None:
            raise AuthenticationException("Unknown email. Try to register.")
        db_pass = self.encryptor.decrypt(user["pass"]).decode("utf-8")
        if user["email"] == data["email"] and db_pass != data["password"]:
            raise AuthenticationException("Wrong password")
        return User.create_from_dict(self.encryptor, user)


class DegiroAuthenticator(Authenticator):
    def __init__(self, encryptor, user_collection):
        super().__init__(encryptor, user_collection)

    def authenticate(self, data):
        degiro = Degiro()
        degiro.login(data["username"], data["password"], data["code"] if len(data["code"]) > 0 else None)
        user = self.collection.find_one({"email": degiro.user["email"], "type": "degiro"})
        if user is None:
            raise AuthenticationException("Unknown email. Try to register.")
        self.collection.find_one_and_update({"email": degiro.user["email"], "type": "degiro"},
                                            {"$set": {"session_id": degiro.session_id, "account_id": degiro.account_id}})

        return DegiroUser.create_from_dict(self.encryptor, user)


class AuthenticatorFactory:
    @staticmethod
    def create(authentication_method, encryptor, user_collection):
        if authentication_method == "email":
            return EmailAuthenticator(encryptor, user_collection)
        elif authentication_method == "degiro":
            return DegiroAuthenticator(encryptor, user_collection)
        else:
            raise AttributeError("Authentication method " + authentication_method + " does not exist.")


class AuthenticationException(Exception):
    def __init__(self, message):
        self.message = message
