from bs4 import BeautifulSoup
from src.extractor.extractor import Extractor
from datetime import datetime
from src.crawler.cleaner import check_key_exists, update_array, clean_key


class FinancialExtractor(Extractor):
    def __init__(self, session):
        self.session = session

    def get_historical_financial_data(self, spans, parent_key=''):
        d = dict()
        column_index = 0
        key = ''
        for index in range(len(spans)):
            value = spans[index].text.replace(',', '')
            if column_index == 0:
                if parent_key == '':
                    parent_key = value
                    key = value
                else:
                    key = parent_key + ' ' + value
                key = clean_key(key)
                d[key] = list()
            elif value.lstrip("-").isnumeric():
                d[key].append(int(value))
            else:
                d.update(self.get_historical_financial_data(spans[index:], parent_key))
                return d
            column_index += 1
        return d

    def get_data(self, data):
        url = "https://finance.yahoo.com/quote/" + data["ticker"] + "/financials?p=" + data["ticker"]
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'lxml')
        temp_data = {"error_financial": 'X-Cache' in r.headers and 'Error' in r.headers['X-Cache'], 'finances': {}}
        for div in soup.find_all("div", {"class": "rw-expnded"}):
            spans = div.find_all("span")
            temp_data['finances'].update(self.get_historical_financial_data(spans, ''))
        return temp_data

    def should_update(self, db_company):
        if ("error_financial" in db_company and db_company["error_financial"]) or ("error_financial" not in db_company):
            return True
        most_recent_quarter = None
        if check_key_exists('most_recent_quarter_(mrq)', db_company):
            most_recent_quarter = db_company['most_recent_quarter_(mrq)']
        return (most_recent_quarter is not None and isinstance(most_recent_quarter, datetime) and
                (datetime.now() - most_recent_quarter).days > 90) or most_recent_quarter is None or \
               (most_recent_quarter is not None and not isinstance(most_recent_quarter, datetime))

    def update(self, data, db_company):
        db_company["error_financial"] = data["error_financial"]
        db_company['finances'] = update_array(db_company['stats'], data['finances'])
        return db_company

    def should_clean(self, db_company):
        return any([" " in key or key.islower() for key in db_company['finances'].keys()])

    def clean(self, db_company):
        db_company['finances'] = {key.lower().replace(" ", "_"): value for key, value in db_company['finances'].items()}
        return db_company
