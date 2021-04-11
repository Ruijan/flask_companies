import math
from datetime import datetime, timedelta
import os
import ccy
import numpy as np
import pycountry
import pymongo
import fmpsdk
from pandas import Series, DataFrame
from urllib.request import urlopen
import json
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
            CompaniesCache.__dividend_calendar = get_dividend_calendar()
            CompaniesCache.__dividend_calendar.sort_index(inplace=True)

    def update_db_company(self, company):
        if company["ticker"] in self:
            company["last_checked"] = datetime.now()
            self[company["ticker"]] = company
            self.__collection.find_one_and_replace({"ticker": company["ticker"]}, company)

    def get(self, key):
        self.fetch_company(key)
        return self[key]

    def get_calendar(self):
        if self.__dividend_calendar is None:
            self.__dividend_calendar = get_dividend_calendar()
        return self.__dividend_calendar

    def get_collection(self):
        return self.__collection

    def fetch_company(self, key):
        today = datetime.now()
        if key not in self or self.should_update_company(key, today):
            company = self.__collection.find_one({"ticker": key})
            if company is None:
                company = dict()
                fetch_company_from_api(key, company, None)
            company["last_checked"] = today
            self[key] = company

    def should_update_company(self, key, today):
        return (today - self[key]["last_update"]).days >= 1 and (today - self[key]["last_checked"]).seconds >= 60

    def should_update_db_company(self, key, today):
        return (today - self[key]["last_update"]).days >= 1

    def update_from_transactions(self, transactions):
        for txn in transactions:
            company = self.get(txn["ticker"])
            should_update = False
            if "currency" not in company or (
                    not isinstance(company["currency"], str) and math.isnan(company["currency"])):
                country = company["country"] if company["country"] != "USA" else "United States"
                company["currency"] = ccy.countryccy(pycountry.countries.get(name=country).alpha_2.lower())
                should_update = True
            if "cagr_3" not in company or np.isnan(company["cagr_3"]):
                div_info = Series(compute_dividends(company))
                company = {**company, **div_info}
                should_update = True
            if company["ticker"] in self.__dividend_calendar.index:
                company["stats"]["ex-dividend_date"] = datetime.strptime(
                    self.__dividend_calendar.loc[company["ticker"]]["date"],
                    "%Y-%m-%d")
                should_update = True
            if should_update:
                self.update_db_company(company)
            company["stats"] = dict(
                (k.replace(" ", "_"), v) if isinstance(k, str) else (k, v) for k, v in company["stats"].items())


def get_dividend_calendar():
    today = datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    data = fmpsdk.dividend_calendar(apikey=os.environ["FINANCE_KEY"], from_date=today.strftime("%Y-%m-%d"),
                                    to_date=(today + timedelta(days=90)).strftime("%Y-%m-%d"))
    return DataFrame.from_dict(data).set_index("symbol")


def fetch_data(base_url):
    response = urlopen(base_url)
    data = response.read().decode("utf-8")
    return json.loads(data)


def fetch_company_from_api(key, company, dividend_date):
    print("Key: " + key)
    api_key = os.environ["FINANCE_KEY"]
    company["profile"] = fmpsdk.company_profile(apikey=api_key, symbol=key)[0]
    company["finances"] = fmpsdk.income_statement(apikey=api_key, symbol=key, period="quarter", limit=100)
    company["stats"] = fmpsdk.key_metrics(apikey=api_key, symbol=key, limit=1)[0]
    company["balance_sheet"] = fmpsdk.balance_sheet_statement(apikey=api_key, symbol=key, period="quarter", limit=100)
    dividends = fmpsdk.historical_stock_dividend(apikey=api_key, symbol=key)
    if "historical" in dividends:
        dividends = dividends["historical"]
        company["dividend_history"] = {dividend["recordDate"]: dividend["adjDividend"] for dividend in dividends
                                       if dividend["recordDate"]}
    else:
        company["dividend_history"] = []
    company["stats"]["ex-dividend_date"] = ""
    if len(dividends) > 0:
        company["stats"]["ex-dividend_date"] = dividend_date if dividend_date is not None else dividends[0]["date"]
        company["stats"]["ex-dividend_date"] = datetime.strptime(company["stats"]["ex-dividend_date"], "%Y-%m-%d")
    dividend_features = Series(get_dividend_features(company["dividend_history"], {},
                                                     company["stats"]["payoutRatio"],
                                                     company["stats"]["dividendYield"]))
    company = {**company, **dividend_features}
    company["last_checked"] = datetime.now()
    company["last_update"] = datetime.now()
    mongo_dbname = 'staging_finance' if os.environ['FLASK_DEBUG'] else 'finance'
    mongo_uri = os.environ['mongo_uri'].strip("'").replace('test', mongo_dbname)
    client = pymongo.MongoClient(mongo_uri)
    client.staging_finance.cleaned_companies.find_one_and_replace({'ticker': company["ticker"]}, company)
