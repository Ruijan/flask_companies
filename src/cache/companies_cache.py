import math
from datetime import datetime

import ccy
import numpy as np
import pycountry
from pandas import Series

from src.extractor.dividend_extractor import compute_dividends


class CompaniesCache(dict):
    __instance = None
    __collection = None

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

    def update_company(self, company):
        if company["ticker"] in self:
            company["last_checked"] = datetime.now()
            self[company["ticker"]] = company
            self.__collection.find_one_and_replace({"ticker": company["ticker"]}, company)

    def get(self, key):
        self.fetch_company(key)
        return self[key]

    def fetch_company(self, key):
        if key not in self:
            company = self.__collection.find_one({"ticker": key})
            company["last_checked"] = datetime.now()
            self[key] = company
        elif (datetime.now() - self[key]["last_update"]).days > 1 and (
                datetime.now() - self[key]["last_checked"]).seconds >= 300:
            company = self.__collection.find_one({"ticker": key})
            company["last_checked"] = datetime.now()
            self[key] = company

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
            if should_update:
                self.update_company(company)
            company["stats"] = dict(
                (k.lower().replace(" ", "_"), v) if isinstance(k, str) else (k, v) for k, v in company["stats"].items())
