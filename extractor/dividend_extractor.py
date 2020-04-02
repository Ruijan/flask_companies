from bs4 import BeautifulSoup
from extractor.extractor import Extractor
from datetime import datetime, date
from crawler.cleaner import is_american_company, check_key_exists, update_array
import pandas as pd
import numpy as np


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
                if row_index > 0 and row.find("td").findNext("td") != None:
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


def get_corrected_div_values(dividends, stock_splits):
    temp_dividends = dividends.copy()
    for key in stock_splits.keys():
        key_time = datetime.strptime(key, "%b %d, %Y")
        if stock_splits[key] > 0:
            temp_dividends = {k: v / stock_splits[key] if datetime.strptime(k, "%b %d, %Y") < key_time else v for
                              k, v
                              in temp_dividends.items()}
    return temp_dividends


def get_yearly_dividends(dividends, stock_splits):
    temp_dividends = get_corrected_div_values(dividends, stock_splits)
    dividend_dates = {key: datetime.strptime(key, "%b %d, %Y") for key in dividends.keys()}
    n_div = dict()
    for k, v in dividend_dates.items():
        key = date(v.year, v.month, 1)
        if key in n_div:
            n_div[key] += temp_dividends[k]
        else:
            n_div[key] = temp_dividends[k]
    years = [key.year for key in n_div.keys()]
    n_div_2 = dict.fromkeys(years, 0)
    for k, v in n_div.items():
        n_div_2[k.year] += n_div[k]
    return pd.DataFrame.from_dict(
        {'Date': list(n_div_2.keys()),
         'values': list(n_div_2.values())}).set_index("Date")


def get_continuous_dividend_payment(yearly_dividends):
    count_years = 0
    shifted_div = yearly_dividends.values[0:-1]
    shifted_dates = yearly_dividends.index[0:-1]
    divdiff = (shifted_div - yearly_dividends.values[1:]) / shifted_div * 100
    datediff = (shifted_dates - yearly_dividends.index[1:]) / shifted_dates * 100
    divdiff = divdiff.flatten()
    if shifted_dates[0] == datetime.today().year:
        divdiff = np.delete(divdiff, 0)
    nb_tot_years = len(divdiff)
    for index in range(nb_tot_years):
        if divdiff[index] < 0 or datediff[index] > 1:
            return count_years
        count_years += 1
    return count_years


def get_cagr(yearly_dividends, years):
    current_year = datetime.now().year
    if current_year - 1 in yearly_dividends.index and current_year - 1 - years in yearly_dividends.index:
        return (np.power(yearly_dividends.loc[current_year - 1] / yearly_dividends.loc[current_year - 1 - years],
                         1 / years) - 1).values[0]
    elif current_year - 2 in yearly_dividends.index and current_year - 2 - years in yearly_dividends.index:
        return (np.power(yearly_dividends.loc[current_year - 2] / yearly_dividends.loc[current_year - 2 - years],
                         1 / years) - 1).values[0]
    return 0


def get_dividend_features(dividends, stock_splits, payout_ratio, current_yield):
    data = {"cagr_1": 0, "cagr_3": 0, "cagr_5": 0, "cagr_10": 0, "continuous_dividend_growth": 0,
            "payout_ratio": payout_ratio, "div_yield": current_yield if current_yield != 'N/A' else 0, "div_score": 0}
    yearly_dividends = get_yearly_dividends(dividends, stock_splits)
    data["cagr_1"] = get_cagr(yearly_dividends, 1)
    data["cagr_3"] = get_cagr(yearly_dividends, 3)
    data["cagr_5"] = get_cagr(yearly_dividends, 5)
    data["cagr_10"] = get_cagr(yearly_dividends, 10)
    data["continuous_dividend_growth"] = get_continuous_dividend_payment(yearly_dividends)
    data["div_score"] = rate_dividends(data)
    return data


def rate_dividends(data):
    score = 0
    max_score = 8
    payout_ratio = 0 if isinstance(data["payout_ratio"], str) else data["payout_ratio"]
    cagr = [data["cagr_1"], data["cagr_3"], data["cagr_5"], data["cagr_10"]]
    score += 2 if data["div_yield"] > 0.05 else 2 * data["div_yield"] / 0.05
    score += 1 if np.std(cagr) < abs(0.2 * np.mean(cagr)) else np.std(cagr) / 0.2 * abs(np.mean(cagr))
    score += 0.33 if data["cagr_1"] > 0.03 else 0.33 * data["cagr_1"] / 0.03
    score += 0.33 if data["cagr_3"] > 0.03 else 0.33 * data["cagr_3"] / 0.03
    score += 0.33 if data["cagr_5"] > 0.03 else 0.33 * data["cagr_5"] / 0.03
    score += 2 if data["continuous_dividend_growth"] > 16 else 2 * data["continuous_dividend_growth"] / 16
    score += 0 if payout_ratio > 1 else 2 * (1 - payout_ratio)

    return score / max_score
