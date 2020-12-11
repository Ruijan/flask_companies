import math
from datetime import datetime, timedelta
import os

import ccy
import numpy as np
import pycountry
from pandas import Series
from urllib.request import urlopen
import json

from src.cache.DividendCalendar import DividendCalendar
from src.extractor.dividend_analyzer import get_dividend_features
from src.extractor.dividend_extractor import compute_dividends


class CompaniesCache(dict):
    __instance = None
    __collection = None
    __dividend_calendar = None

    @staticmethod
    def get_instance():
        if CompaniesCache.__instance is None:
            CompaniesCache()
        return CompaniesCache.__instance

    def __init__(self, collection):
        super().__init__()
        if CompaniesCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            CompaniesCache.__instance = self
            CompaniesCache.__collection = collection
            #CompaniesCache.__dividend_calendar = DividendCalendar(datetime.today(), period=60).fetch_calendar()
            CompaniesCache.__dividend_calendar.sort_index(inplace=True)

    def update_db_company(self, company):
        if company["ticker"] in self:
            company["last_checked"] = datetime.now()
            self[company["ticker"]] = company
            self.__collection.find_one_and_replace({"ticker": company["ticker"]}, company)

    def get(self, key):
        self.fetch_company(key)
        return self[key]

    def fetch_company(self, key):
        if key not in self:
            today = datetime.now()
            company = self.__collection.find_one({"ticker": key})
            company["last_checked"] = today
            self[key] = company

    def should_update_company(self, key, today):
        #return (today - self[key]["last_update"]).days >= 0 and (today - self[key]["last_checked"]).seconds >= 65
        return (today - self[key]["last_update"]).days > 1 and (today - self[key]["last_checked"]).seconds >= 300

    def update_from_transactions(self, transactions):
        for txn in transactions:
            company = self.get(txn["ticker"])
            should_update = False
            if "currency" not in company or (not isinstance(company["currency"], str) and math.isnan(company["currency"])):
                country = company["country"] if company["country"] != "USA" else "United States"
                company["currency"] = ccy.countryccy(pycountry.countries.get(name=country).alpha_2.lower())
                should_update = True
            if "cagr_3" not in company or np.isnan(company["cagr_3"]):
                div_info = Series(compute_dividends(company))
                company = {**company, **div_info}
                should_update = True
            if company["ticker"] in self.__dividend_calendar.index:
                company["stats"]["ex-dividend_date"] = datetime.strptime(self.__dividend_calendar.loc[company["ticker"]]["date"],
                                                                         "%Y-%m-%d")
                should_update = True
            if should_update:
                self.update_db_company(company)
            company["stats"] = dict(
                (k.replace(" ", "_"), v) if isinstance(k, str) else (k, v) for k, v in company["stats"].items())


def get_dividend_calendar():
    today = datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    base_url = "https://financialmodelingprep.com/api/v3/stock_dividend_calendar" + "?from=" + \
               today.strftime("%Y-%m-%d") + "&to=" + (today + timedelta(days=90)).strftime("%Y-%m-%d") + \
               "&apikey=" + os.environ["FINANCE_KEY"]
    return fetch_data(base_url)


def fetch_data(base_url):
    response = urlopen(base_url)
    data = response.read().decode("utf-8")
    return json.loads(data)


def fetch_company_from_api(key, cache):
    print("fetch company")
    base_url = "https://financialmodelingprep.com/api/v3/"
    suffix_url = "apikey=" + os.environ["FINANCE_KEY"]
    profile_url = base_url + "profile/" + key + "?period=quarter&limit=400&" + suffix_url
    finance_url = base_url + "income-statement/" + key + "?period=quarter&limit=400&" + suffix_url
    dividend_url = base_url + "historical-price-full/stock_dividend/" + key + "?" + suffix_url
    stats_url = base_url + "key-metrics/" + key + "?limit=1&" + suffix_url
    cache[key]["profile"] = fetch_data(profile_url)[0]
    cache[key]["finances"] = fetch_data(finance_url)
    cache[key]["stats"] = fetch_data(stats_url)[0]
    dividends = fetch_data(dividend_url)["historical"]
    cache[key]["dividend_history"] = {dividend["recordDate"]: dividend["adjDividend"]
                                     for dividend in dividends
                                     if dividend["recordDate"]}
    cache[key]["stats"]["ex-dividend_date"] = ""
    if len(dividends) > 0:
        is_in_calendar = key in cache.__dividend_calendar.index
        cache[key]["stats"]["ex-dividend_date"] = cache.__dividend_calendar.loc[key]["date"] if is_in_calendar else \
            dividends[0]["date"]
        cache[key]["stats"]["ex-dividend_date"] = datetime.strptime(cache[key]["stats"]["ex-dividend_date"], "%Y-%m-%d")
    dividend_features = Series(get_dividend_features(cache[key]["dividend_history"], {},
                                                     cache[key]["stats"]["payoutRatio"],
                                                     cache[key]["stats"]["dividendYield"]))
    cache[key] = {**cache[key], **dividend_features}
    cache[key]["last_checked"] = datetime.now()
    cache[key]["last_update"] = datetime.now()
    cache.__collection.find_one_and_replace({'_id': cache[key]["_id"]}, cache[key])
