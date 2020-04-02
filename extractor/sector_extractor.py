from extractor.extractor import Extractor
from bs4 import BeautifulSoup
import pandas as pd


class SectorExtractor(Extractor):
    def __init__(self, session):
        self.session = session

    def get_data(self, data):
        url = "https://finance.yahoo.com/quote/" + data["ticker"] + "/profile?p=" + data["ticker"]
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'html.parser')
        temp_data = {"error_sector": bool('X-Cache' in r.headers and 'Error' in r.headers['X-Cache'])}
        for p in soup.find_all("p", {"class": "D(ib) Va(t)"}):
            sector = p.find("span")
            temp_data[sector.text.lower()] = sector.findNext("span").text
            industry = sector.findNext("span").findNext("span")
            temp_data[industry.text.lower()] = industry.findNext("span").text
        return temp_data

    def should_update(self, db_company):
        return ("error_sector" in db_company and db_company["error_sector"]) or ("error_sector" not in db_company) \
               or not isinstance(db_company["sector"], str) or db_company["sector"] == "NaN"

    def update(self, data, db_company):
        db_company.append(pd.Series(data))
        return db_company

    def should_clean(self, db_company):
        return False

    def clean(self, db_company):
        return db_company
