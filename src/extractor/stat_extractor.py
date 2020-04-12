from src.extractor.extractor import Extractor
from src.crawler.cleaner import is_date, str_amount_to_number, clean_key, update_array
from datetime import datetime
from bs4 import BeautifulSoup
from numpy import any


class StatExtractor(Extractor):
    def __init__(self, session):
        self.session = session

    def get_data(self, data):
        url = "https://finance.yahoo.com/quote/" + data["ticker"] + "/key-statistics?p=" + data["ticker"]
        r = self.session.get(url)
        page_body = r.text
        soup = BeautifulSoup(page_body, 'html.parser')
        temp_data = {"error_stats": bool('X-Cache' in r.headers and 'Error' in r.headers['X-Cache']), 'stats': {}}
        for table in soup.findAll("section", {'data-test': "qsp-statistics"}):
            for row in table.findAll("tr"):
                value = row.find("td").findNext("td").text
                key = clean_key(row.find("td").text)
                if 'N/A' not in value:
                    if is_date(value):
                        value = datetime.strptime(value, '%b %d, %Y')
                    elif 'factor' in key:
                        factors = value.split(':')
                        if abs(float(factors[1])) > 0.1:
                            value = float(factors[0]) / float(factors[1])
                    else:
                        value = str_amount_to_number(value)
                temp_data['stats'][key] = value
        return temp_data

    def should_update(self, db_company):
        return ("error_stats" in db_company and db_company["error_stats"]) or ("error_stats" not in db_company) or \
               ((datetime.today() - db_company["last_update"]).days >= 1)

    def update(self, data, db_company):
        db_company["error_stats"] = data["error_stats"]
        db_company['stats'] = update_array(db_company['stats'], data['stats'])
        return db_company

    def should_clean(self, db_company):
        return any([" " in key or key.islower() for key in db_company['stats'].keys()])

    def clean(self, db_company):
        db_company['stats'] = {key.lower().replace(" ", "_"): value for key, value in db_company['stats'].items()}
        return db_company
