from src.extractor.extractor import Extractor
from bs4 import BeautifulSoup
from src.crawler import update_array
from datetime import datetime


class StockSplitExtractor(Extractor):
    def __init__(self, session):
        self.session = session

    def get_data(self, data):
        url = "https://finance.yahoo.com/quote/" + data["ticker"] + "/history?period1=730422000&period2=1739836800&interval" \
                                                            "=div%7Csplit&filter=split&frequency=1d "
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'html.parser')
        row_index = 0
        temp_data = {"error_splits": bool('X-Cache' in r.headers and 'Error' in r.headers['X-Cache']), "stock_splits": dict()}
        for table in soup.findAll("table", {"class": "W(100%) M(0)"}):
            for row in table.findAll("tr"):
                if row_index > 0 and row.find("td").findNext("td") is not None:
                    date = row.find("td").text
                    value = row.find("td").findNext("td").text
                    if 'Stock Split' in value:
                        value = value.replace('Stock Split', '').strip(' ')
                        factors = value.split(':')
                        if float(factors[1]) > 0:
                            value = float(factors[0]) / float(factors[1])
                            temp_data["stock_splits"][date] = float(value)
                row_index += 1
        return temp_data

    def should_update(self, db_company):
        return ("error_splits" in db_company and db_company["error_splits"]) or ("error_splits" not in db_company) or \
               ((datetime.today() - db_company["last_update"]).days >= 1)

    def update(self, data, db_company):
        db_company["error_splits"] = data["error_splits"]
        db_company["stock_splits"] = update_array(db_company["stock_splits"], data["stock_splits"])
        return db_company

    def should_clean(self, db_company):
        return False

    def clean(self, db_company):
        return db_company
