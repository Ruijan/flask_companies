import yfinance as yf


class HistoryCache(dict):
    __instance = None

    @staticmethod
    def get_instance():
        if HistoryCache.__instance is None:
            HistoryCache()
        return HistoryCache.__instance

    def __init__(self):
        if HistoryCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            HistoryCache.__instance = self

    def get(self, key):
        if key not in self:
            self[key] = yf.Ticker(key).history(period="max")
        return self[key]
