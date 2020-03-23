import time
from datetime import datetime, timedelta
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

    def get(self, key, start_date=None, end_date=None, period="max"):
        if end_date is None:
            end_date = datetime.today()
        if start_date is None:
            if period == "max":
                start_date = datetime(1900, 1, 1)
            elif period == "1d":
                start_date = end_date - timedelta(days=1)
            elif period == "5d":
                start_date = end_date - timedelta(days=5)
            elif period == "1m":
                start_date = end_date - timedelta(months=1)
            elif period == "3m":
                start_date = end_date - timedelta(months=3)
            elif period == "6m":
                start_date = end_date - timedelta(months=6)
            elif period == "1y":
                start_date = end_date - timedelta(years=1)
            elif period == "3y":
                start_date = end_date - timedelta(years=3)
            elif period == "5y":
                start_date = end_date - timedelta(years=5)
            elif period == "10y":
                start_date = end_date - timedelta(years=10)

        should_update = False
        if key not in self:
            self[key] = {"history": yf.Ticker(key).history(start=start_date, end=end_date),
                         "last_update": datetime.now(),
                         "start_date": start_date,
                         "end_date": end_date}
        elif key in self and start_date < self[key]["start_date"]:
            added_history = yf.Ticker(key).history(start=start_date, end=self[key]["start_date"] - timedelta(days=1))
            self[key]["history"] = self[key]["history"].append(added_history).sort_values(by=["Date"], ascending=True)
            self[key]["start_date"] = start_date
        half_day_seconds = 24 * 24 * 12
        if self[key] is None or (datetime.now() - self[key]["last_update"]).seconds > half_day_seconds:
            should_update = True

        if should_update:
            self[key] = {"history": yf.Ticker(key).history(period="max"), "last_update": datetime.now()}
        hist = self[key]["history"].copy()
        mask = (hist.index >= start_date) & (hist.index <= end_date)
        return hist.loc[mask]

    def get_last_day(self, key):
        if key not in self:
            self[key] = {"history": yf.Ticker(key).history(period="1d"),
                         "last_update": datetime.now(),
                         "start_date": datetime.today() - datetime.timedelta(days=1),
                         "end_date": datetime.today()}
        return self[key]["history"].loc[self[key]["history"].index.max(), :]

