import time
from datetime import datetime
import pandas as pd
import yfinance as yf


class LocalHistoryCache(dict):
    __instance = None
    __collection = None

    @staticmethod
    def get_instance():
        if LocalHistoryCache.__instance is None:
            LocalHistoryCache()
        return LocalHistoryCache.__instance

    def __init__(self, collection):
        if LocalHistoryCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            LocalHistoryCache.__instance = self
            LocalHistoryCache.__collection = collection

    def get(self, key):
        should_update = False
        if key not in self:
            self[key] = {"history": yf.Ticker(key).history(period="max"), "last_update": datetime.now()}
        half_day_seconds = 24 * 24 * 12
        if self[key] is None or (datetime.now() - self[key]["last_update"]).seconds > half_day_seconds:
            should_update = True

        if should_update:
            self[key] = {"history": yf.Ticker(key).history(period="max"), "last_update": datetime.now()}
        return self[key]["history"]
