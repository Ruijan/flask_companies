import copy
from datetime import datetime
from numpy import mean

from src.currency import Currency


class Position(dict):
    def __init__(self, name, sector, industry, country, currency, ex_div_date, div_frequency, current_price):
        super().__init__()
        self["daily_change"] = 0
        self["daily_change_perc"] = 0
        self["total_change"] = 0
        self["total_change_perc"] = 0
        self["previous_total"] = 0
        self["total"] = 0
        self["shares"] = 0
        self["dividends"] = 0
        self["name"] = name
        self["sector"] = sector
        self["industry"] = industry
        self["country"] = country
        if not isinstance(currency, Currency):
            raise AttributeError("Currency must be Currency type, not", str(type(currency)))
        self["currency"] = currency
        self["ex_dividend_date"] = ex_div_date
        self["dividend_frequency"] = div_frequency
        self["current_price"] = current_price

    @staticmethod
    def create_from_dict(position):
        new_position = Position(position["name"], position["sector"], position["industry"], position["country"],
                                Currency(position["currency"]), position["ex_dividend_date"], position["dividend_frequency"],
                                position["current_price"])
        new_position["daily_change"] = position["daily_change"]
        new_position["daily_change_perc"] = position["daily_change"]
        new_position["total_change"] = position["total_change"]
        new_position["total_change_perc"] = position["total_change_perc"]
        new_position["previous_total"] = position["previous_total"]
        new_position["total"] = position["total"]
        new_position["shares"] = position["shares"]
        new_position["dividends"] = position["dividends"]
        return new_position

    @staticmethod
    def compute_div_frequency(dividend_history):
        div_freq = dict()
        for key, _ in dividend_history.items():
            year = datetime.strptime(key, "%Y-%m-%d").year
            if year not in div_freq:
                div_freq[year] = 0
            div_freq[year] += 1
        div_freq = [(year, value) for year, value in div_freq.items()]
        div_freq = sorted(div_freq, key=lambda x: x[0], reverse=True)
        div_freq = [x[1] for x in div_freq]
        return round(mean(div_freq[1:5]))

    def add_transaction(self, txn, txn_hist, c_div):
        current_close = txn_hist["Close"][-1] if len(txn_hist["Close"]) > 0 else txn["total"]
        previous_close = txn_hist["Close"][-2] if len(txn_hist["Close"]) > 1 else txn["total"]
        previous_date = txn_hist.index[-1] if len(txn_hist.index) > 0 else datetime.today()
        self["shares"] += txn["shares"]
        self["current_price"] = current_close/txn["shares"]
        self["dividends"] += c_div
        self["total"] += txn["total"]
        if (datetime.today() - previous_date).days >= 1:
            self["daily_change"] += 0
        else:
            self["daily_change"] += current_close - previous_close
        self["previous_total"] += previous_close
        self["total_change"] += current_close - txn["total"]
        self["total_change_perc"] = self["total_change"] / self["total"] * 100
        self["daily_change_perc"] = self["daily_change"] / self["previous_total"] * 100

    def subtract_transaction(self, txn, txn_hist, c_div):
        self["shares"] -= txn["shares"]
        self["dividends"] -= c_div
        self["total"] -= txn["total"]
        previous_amount = (txn_hist["Close"][-2] if txn_hist.shape[0] > 1 else txn["total"])
        if (datetime.today() - txn_hist.index[-1]).days >= 1:
            self["daily_change"] += 0
        else:
            self["daily_change"] -= txn_hist["Close"][-1] - previous_amount
        self["previous_total"] -= previous_amount
        self["total_change"] -= txn_hist["Close"][-1] - txn["total"]

    @property
    def is_empty(self):
        return self["shares"] == 0

    def json_format(self):
        self_copy = copy.deepcopy(self)
        self_copy["currency"] = self["currency"].short
        return self_copy
