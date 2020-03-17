import requests
from datetime import datetime
from multiprocessing.pool import ThreadPool

from extractor.dividend_extractor import DividendExtractor
from extractor.financial_extractor import FinancialExtractor
from extractor.sector_extractor import SectorExtractor
from extractor.stat_extractor import StatExtractor
from extractor.stock_split_extractor import StockSplitExtractor


class CompanyExtractor:
    extractors = dict()
    session = None
    pool = None

    def __init__(self):
        self.session = requests.Session()
        self.pool = ThreadPool(processes=5)
        self.extractors["Stats"] = StatExtractor(self.session)
        self.extractors["Sector"] = SectorExtractor(self.session)
        self.extractors["Finance"] = FinancialExtractor(self.session)
        self.extractors["StockSplits"] = StockSplitExtractor(self.session)
        self.extractors["Dividends"] = DividendExtractor(self.session)

    def load_data_async(self, company, logs):
        status = "OK"
        async_extractors = dict()

        errors_before = sum([company[key] for key in company.keys() if "error" in key])

        for key, extractor in self.extractors.items():
            if extractor.should_update(company):
                async_extractors[key] = self.pool.apply_async(extractor.get_data, company.to_dict())
        for key, extractor in async_extractors.items():
            company = self.extractors.update(company, extractor.get())
        errors_after = sum([company[key] for key in company.keys() if "error" in key])
        if errors_after > errors_before:
            status = "ERROR"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs += "[" + timestamp + "] {:^8}".format(status) + "Ticker: {:^6}".format(company["ticker"])
        return company, status

    def load_data(self, company, logs):
        status = "OK"
        errors_before = sum([company[key] for key in company.keys() if "error" in key])
        for key, extractor in self.extractors.items():
            if extractor.should_update(company):
                company = extractor.update(extractor.get_data(company), company)
            if extractor.should_clean(company):
                company = extractor.clean(company)
        keys = list(company.index)
        errors_after = sum([company[key] for key in keys if "error" in key])
        if errors_after > errors_before:
            status = "ERROR"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs += "[" + timestamp + "] {:^8}".format(status) + "Ticker: {:^6}".format(company["ticker"] + "\n")
        return company, status, logs

    def reset_session(self):
        self.session.close()
        self.session = requests.Session()



