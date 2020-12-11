from bs4 import BeautifulSoup

from src.extractor.dividend_analyzer import get_dividend_features
from src.extractor.extractor import Extractor
from datetime import datetime
from src.crawler.cleaner import is_american_company, check_key_exists, update_array
import pandas as pd


class DividendExtractor(Extractor):
    def __init__(self, session):
        self.session = session

    def get_data(self, data):
        if is_american_company(data["country"]):
            temp_data = self.get_dividends_from_dividata(data["ticker"])
        if not is_american_company(data["country"]) or ("error_dividends" in data and data["error_dividends"]) or (
                len(data["dividend_history"]) == 0):
            temp_data = self.get_dividends_from_yahoo(data["ticker"])
        return temp_data

    def get_dividends_from_yahoo(self, ticker):
        url = "https://finance.yahoo.com/quote/" + ticker + "/history?period1=730422000&period2=1739836800&interval" \
                                                            "=div%7Csplit&filter=div&frequency=1d "
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'html.parser')
        row_index = 0
        data = {"error_dividends": 'X-Cache' in r.headers and 'Error' in r.headers['X-Cache'],
                "dividend_history": dict()}
        for table in soup.findAll("table", {"class": "W(100%) M(0)"}):
            for row in table.findAll("tr"):
                if row_index > 0 and row.find("td").findNext("td") is not None:
                    date = row.find("td").text
                    value = row.find("td").findNext("td").text
                    if 'Dividend' in value:
                        value = value.replace('Dividend', '').strip(' ')
                        if value is not '':
                            data["dividend_history"][date] = float(value)
                row_index += 1
        return data

    def get_dividends_from_dividata(self, ticker):
        url = "https://dividata.com/stock/" + ticker + "/dividend"
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'lxml')
        data = {"error_dividends": 'X-Cache' in r.headers and 'Error' in r.headers['X-Cache'],
                "dividend_history": dict()}
        for div in soup.find_all("table"):
            for tr in div.find_all("tr"):
                columns = tr.find_all("td")
                if len(columns) > 1:
                    data["dividend_history"][columns[0].text] = float(columns[1].text[1:].replace(',', ''))
        return data

    def should_update(self, db_company):
        if 'dividend_history' not in db_company:
            return True
        if "error_dividends" in db_company and db_company["error_dividends"]:
            return True
        should_update = True
        dates = [datetime.strptime(key, '%b %d, %Y') for key in db_company['dividend_history'].keys()]
        dates.sort(reverse=True)
        if check_key_exists('Ex-Dividend Date', db_company):
            exdiv_date = db_company['Ex-Dividend Date']
            if isinstance(exdiv_date, str) and 'N/A' not in exdiv_date:
                exdiv_date = datetime.strptime(exdiv_date, '%b %d, %Y')
            if not isinstance(exdiv_date, str) and len(dates) > 0 and exdiv_date < dates[0]:
                should_update = False
        return should_update

    def update(self, data, db_company):
        db_company["error_dividends"] = data["error_dividends"]
        db_company['dividend_history'] = update_array(db_company['dividend_history'],
                                                      data['dividend_history'])
        if not data["error_dividends"]:
            div_infos = pd.Series(compute_dividends(db_company))
            db_company = db_company.append(div_infos)
        return db_company

    def should_clean(self, db_company):
        return False

    def clean(self, db_company):
        return db_company


def compute_dividends(row):
    if "payout_ratio" in row["stats"] and "forward_annual_dividend_yield" in row["stats"]:
        return get_dividend_features(row["dividend_history"], row["stock_splits"],
                                     row["stats"]["payout_ratio"],
                                     row["stats"]["forward_annual_dividend_yield"])
    return get_dividend_features(row["dividend_history"], row["stock_splits"], 0, 0)


