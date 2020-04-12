import time
from datetime import datetime, timedelta
import yfinance as yf


def get_range(end_date, period, start_date):
    if end_date is None:
        end_date = datetime.today()
    if start_date is None:
        if period == "max":
            start_date = datetime(1900, 1, 1)
        else:
            amount = int(period[0])
            element_of_time = period[1]
            if element_of_time == "d":
                start_date = end_date - timedelta(days=amount)
            elif element_of_time == "w":
                start_date = end_date - timedelta(weeks=amount)
            elif element_of_time == "m":
                start_date = end_date - timedelta(weeks=4*amount)
            elif element_of_time == "y":
                start_date = end_date - timedelta(weeks=52 * amount)
    return end_date, start_date


class LocalHistoryCache(dict):
    __instance = None
    __collection = None

    @staticmethod
    def get_instance():
        if LocalHistoryCache.__instance is None:
            LocalHistoryCache()
        return LocalHistoryCache.__instance

    def __init__(self, collection):
        super().__init__()
        if LocalHistoryCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            LocalHistoryCache.__instance = self
            LocalHistoryCache.__collection = collection

    def get(self, key, start_date=None, end_date=None, period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        self[key] = self.fetch_history(key, start_date, end_date, period)
        hist = self[key]["history"].copy()
        mask = (hist.index >= start_date) & (hist.index <= end_date)
        return hist.loc[mask]

    def get_last_day(self, key):
        if key not in self:
            self[key] = {"history": yf.Ticker(key).history(period="1d"),
                         "last_update": datetime.now(),
                         "start_date": datetime.today() - timedelta(days=1),
                         "end_date": datetime.today()}
            self[key]["history"] = self[key]["history"].loc[~self[key]["history"].index.duplicated(keep='first')]
        last_day_close = self[key]["history"].loc[self[key]["history"].index.max(), :]
        return last_day_close

    def fetch_history(self, key, start_date=None, end_date=None, period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        temp_data = None
        if key not in self:
            start = time.time()
            temp_data = {"history": yf.Ticker(key).history(start=start_date, end=end_date),
                         "last_update": datetime.now(),
                         "start_date": start_date,
                         "end_date": end_date}
            print("GET COMPANY HISTORY %s seconds ---" % (time.time() - start))
        elif key in self:
            temp_data = self[key].copy()
            diff_time = self[key]["start_date"] - start_date
            if diff_time.days > 0:
                added_history = yf.Ticker(key).history(start=start_date,
                                                       end=self[key]["start_date"] - timedelta(days=1))
                temp_data["history"] = temp_data["history"].append(added_history).sort_values(by=["Date"],
                                                                                              ascending=True)

                temp_data["start_date"] = start_date
        temp_data["history"]["Close"] = temp_data["history"]["Close"].fillna(method='ffill').fillna(method='bfill')
        temp_data["history"] = temp_data["history"].loc[~temp_data["history"].index.duplicated(keep='first')]
        fifteen_minutes = 60 * 15
        if (datetime.now() - temp_data["last_update"]).seconds > fifteen_minutes:
            today_hist = yf.Ticker(key).history(period='1d')
            index = today_hist.index[0]
            new_data = today_hist.iloc[0]
            temp_data["history"].loc[index] = new_data
            temp_data["last_update"] = datetime.now()
            temp_data["end_date"] = datetime.today()
        return temp_data

    def fetch_multiple_histories(self, keys, start_date=None, end_date=None, period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        keys_to_download = [key for key in keys if key not in self]
        keys_in_cache = [key for key in keys if key in self]
        results = {}
        if len(keys_to_download) > 0:
            tickers = " ".join(keys_to_download)
            data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', auto_adjust=True, actions=True)

            for key in keys_to_download:
                if len(keys_to_download) > 1:
                    temp_data = data[key]
                else:
                    temp_data = data
                temp_data = temp_data.fillna(method='ffill')
                temp_data = temp_data.fillna(method='bfill')
                temp_data = temp_data.loc[~temp_data.index.duplicated(keep='first')]
                results[key] = {"history": temp_data,
                                "last_update": datetime.now(),
                                "start_date": start_date,
                                "end_date": end_date}
        for key in keys_in_cache:
            results[key] = self[key]
        return results

    def update_history(self, key, new_value):
        self[key] = new_value
