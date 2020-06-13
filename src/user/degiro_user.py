from datetime import datetime
from bson import ObjectId
from src.user.user import User


class DegiroUser(User):
    def __init__(self, user_id, first_name, last_name, email, creation_date, last_connection, location, encryption,
                 session_id, account_id):
        super().__init__(user_id, first_name, last_name, email, creation_date, last_connection, location, encryption)
        self.session_id = session_id
        self.account_id = account_id
        self.type = "degiro"

    @staticmethod
    def create_from_db(collection, user_id, encryption):
        user = collection.find_one({"_id": ObjectId(user_id)})
        return DegiroUser.create_from_dict(encryption, user)

    @staticmethod
    def create_from_dict(encryption, user):
        return DegiroUser(user["_id"],
                          encryption.decrypt(user["first_name"]).decode(),
                          encryption.decrypt(user["last_name"]).decode(),
                          user["email"],
                          user["creation_date"],
                          user["last_connection"],
                          user["geolocation"],
                          encryption,
                          user["session_id"],
                          user["account_id"])

    def to_db_dict(self):
        now = datetime.now()
        data = {"first_name": self.encryption.encrypt(self.first_name.encode()),
                "last_name": self.encryption.encrypt(self.last_name.encode()),
                "type": "degiro",
                "email": self.email,
                "session_id": self.session_id,
                "account_id": self.account_id,
                "creation_date": now,
                "last_connection": now,
                "geolocation": self.location}
        return data
