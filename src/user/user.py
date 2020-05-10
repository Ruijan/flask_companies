from datetime import datetime
from bson import ObjectId


class User:
    def __init__(self, user_id, first_name, last_name, email, creation_date, last_connection, location, encryption):
        self.id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.type = "email"
        self.creation_date = creation_date
        self.last_connection = last_connection
        self.location = location
        self.encryption = encryption

    @staticmethod
    def does_email_exist(collection, email):
        user = None
        try:
            user = collection.find_one({"email": email})
        except:
            pass
        return user is not None

    @staticmethod
    def does_id_exist(collection, id):
        user = None
        try:
            user = collection.find_one({"_id": ObjectId(id)})
        except:
            pass
        return user is not None

    @staticmethod
    def create_from_db(collection, user_id, encryption):
        user = collection.find_one({"_id": ObjectId(user_id)})
        return User.create_from_dict(encryption, user)

    @staticmethod
    def create_from_dict(encryption, user):
        return User(user["_id"], encryption.decrypt(user["first_name"]).decode(),
                    encryption.decrypt(user["last_name"]).decode(),
                    user["email"], user["creation_date"],
                    user["last_connection"], user["geolocation"], encryption)

    def save_to_database(self, collection):
        collection.find_one_and_update({"_id": ObjectId(self.id)}, {'$set': self.to_db_dict()})

    def update_password(self, collection, password):
        collection.find_one_and_update({"_id": ObjectId(self.id)},
                                       {'$set': {"pass": self.encryption.encrypt(password.encode())}})

    def to_db_dict(self):
        now = datetime.now()
        data = {"first_name": self.encryption.encrypt(self.first_name.encode()),
                "last_name": self.encryption.encrypt(self.last_name.encode()),
                "type": "email",
                "email": self.email,
                "creation_date": now, "last_connection": now, "geolocation": self.location}
        return data
