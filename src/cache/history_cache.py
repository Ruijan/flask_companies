import time
from datetime import datetime
import pandas as pd
import yfinance as yf


class HistoryCache(dict):
    __instance = None
    __collection = None

    @staticmethod
    def get_instance():
        if HistoryCache.__instance is None:
            HistoryCache()
        return HistoryCache.__instance

    def __init__(self, collection):
        if HistoryCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            HistoryCache.__instance = self
            HistoryCache.__collection = collection

    def get(self, key):
        should_update = False
        should_create = False
        if key not in self:
            self[key] = self.__collection.find_one({"ticker": key})
        half_day_seconds = 24 * 24 * 12
        if self[key] is None or (datetime.now() - self[key]["last_update"]).seconds > half_day_seconds:
            should_update = True

        if self[key] is None:
            should_create = True
            self[key] = {"ticker": key, "last_update": datetime.now(), "history": dict()}

        if should_update:
            history = yf.Ticker(key).history(period="10y")
            self[key]["history"] = history
            self[key]["last_update"] = datetime.now()
            db_company = self[key].copy()
            db_company["history"].reset_index(inplace=True)
            db_company["history"].index = list(map(str, db_company["history"].index))
            db_company["history"] = db_company["history"].to_dict()
            if should_create:
                self.__collection.insert_one(db_company)
            else:
                self.__collection.find_one_and_replace({"ticker": db_company["ticker"]}, db_company)

        if not isinstance(self[key]["history"], pd.DataFrame):
            self[key]["history"] = pd.DataFrame.from_dict(self[key]["history"])
        if "Date" in self[key]["history"]:
            self[key]["history"] = self[key]["history"].set_index("Date")
        return self[key]["history"]
