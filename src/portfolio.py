from pandas import DataFrame, Series
from datetime import datetime, timedelta
import numpy as np


class Portfolio:
    def __init__(self, name, user, stats, history, last_update, positions, currency, identifier, total, current,
                 transactions):
        self.name = name
        self.user = user
        self.stats = stats
        self.history = history if history is not None else DataFrame()
        self.last_update = last_update
        self.positions = positions
        self.currency = currency
        self.id = identifier
        self.total = total
        self.current = current
        self.transactions = transactions
        self.index_transaction = int(np.max([txn["id"] for txn in transactions]))
        pass

    @staticmethod
    def retrieve_from_database(database, user_email, name):
        portfolio = database.find_one({"email": user_email, "name": name})
        if "history" in portfolio:
            portfolio["history"] = DataFrame.from_dict(portfolio["history"])
            if portfolio["history"].index.name != "Date":
                portfolio["history"].set_index("Date", inplace=True)
        return Portfolio(portfolio["name"], portfolio["email"], portfolio["stats"], portfolio["history"],
                         portfolio["last_update"], portfolio["summary"], portfolio["currency"], portfolio["_id"],
                         portfolio["total"], portfolio["current"], portfolio["transactions"])

    def update(self, cache, cache_companies, db_portfolio):
        if len(self.transactions) > 0:
            now = datetime.now()
            diff_time = (now - self.last_update)
            if 60 < diff_time.seconds and diff_time.days < 1 and now.weekday() < 5:
                self.process_portfolio(cache, cache_companies, refresh=True)
            else:
                self.process_portfolio(cache, cache_companies)
        online_portfolio = self.to_dict().copy()
        online_portfolio["history"] = self.history.reset_index().to_dict(orient="list")
        online_portfolio["last_update"] = now
        db_portfolio.find_one_and_replace({"email": self.user, "name": self.name}, online_portfolio)

    def process_portfolio(self, cache, cache_companies, refresh=False):
        hist = DataFrame()
        ref_hist = DataFrame()

        self.positions = dict()
        self.stats = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                      "years_of_growth": 0}
        for txn in self.transactions:
            company = cache_companies.get(txn["ticker"])
            temp_txn = txn.copy()
            if refresh:
                date = datetime.strptime(temp_txn["date"], "%Y-%m-%d")
                new_date = datetime.today() - timedelta(days=1)
                temp_txn["date"] = datetime.strftime(new_date if date < new_date else date, "%Y-%m-%d")
            current_time = datetime.now()
            if current_time.weekday() > 4:
                temp_txn["date"] = datetime.strftime(current_time.date() - timedelta(days=current_time.weekday()),
                                                     "%Y-%m-%d")
            txn_hist = compute_history(cache, self.currency, temp_txn, company["currency"], company["country"])
            hist = add_txn_hist(hist, txn_hist)
            ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
            ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
            conversion_rate = get_current_conversion_rate(company["currency"], self.currency, cache)
            c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
            self.add_txn_to_stats(c_div, company, temp_txn)
            self.add_txn_to_positions(c_div, company, temp_txn, txn_hist)
        for ticker, position in self.positions.items():
            position["total_change_perc"] = position["total_change"] / position["total"] * 100
            position["daily_change_perc"] = position["daily_change"] / position["previous_total"] * 100
            position["current_price"] = cache.get_last_day(ticker)["Close"]
        if self.transactions:
            hist["S&P500"] = ref_hist["Close"]
        self.compute_stats(hist)

    def add_transaction(self, data, cache, companies_cache):
        self.index_transaction += 1
        data["id"] = self.index_transaction
        data["shares"] = int(data["shares"])
        data["price_COS"] = float(data["price_COS"])
        data["price"] = float(data["price"])
        data["fees"] = float(data["fees"])
        data["total"] = data["price"] * data["shares"]
        data.pop("action")
        self.transactions.append(data)
        self.total += data["total"]
        company = companies_cache.get(data["ticker"])
        txn_history = compute_history(cache, self.currency, data, company["currency"], company["country"])
        ref_hist = DataFrame() if self.history.empty else self.history[
            ["S&P500", "Date", "Amount", "Net_Dividends", "Dividends"]]
        if not ref_hist.empty:
            ref_hist = ref_hist.rename(columns={"S&P500": "Close"}).set_index("Date")
        hist = DataFrame() if not self.history else self.history.drop("S&P500", axis=1).set_index("Date")
        hist = add_txn_hist(hist, txn_history)
        temp_txn = data.copy()
        ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
        ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
        conversion_rate = get_current_conversion_rate(company["currency"], self.currency, cache)
        c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
        self.add_txn_to_positions(c_div, company, data, txn_history)
        self.stats = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                      "years_of_growth": 0}
        for txn in self.transactions:
            conversion_rate = get_current_conversion_rate(company["currency"], self.currency, cache)
            c_div = company["stats"]["forward_annual_dividend_rate"] * txn["shares"] * conversion_rate
            self.add_txn_to_stats(c_div, company, txn)
        for ticker, position in self.positions.items():
            position["total_change_perc"] = position["total_change"] / position["total"] * 100
            position["daily_change_perc"] = position["daily_change"] / position["previous_total"] * 100
            position["current_price"] = cache.get_last_day(ticker)["Close"]
        if self.transactions:
            hist["S&P500"] = ref_hist["Close"]
        self.compute_stats(hist)

    def remove_transaction(self, data, cache, companies_cache):
        index = [index for index in range(len(self.transactions))
                 if self.transactions[index]["id"] == int(data["id"])]
        txn = self.transactions.pop(index[0])
        self.total -= txn["total"]
        company = companies_cache.get(txn["ticker"])
        txn_history = compute_history(cache, self.currency, txn, company["currency"], company["country"])
        ref_hist = DataFrame() if self.history.empty else self.history[
            ["S&P500", "Date", "Amount", "Net_Dividends", "Dividends"]]
        if not ref_hist.empty:
            ref_hist = ref_hist.rename(columns={"S&P500": "Close"}).set_index("Date")
        hist = DataFrame() if not self.history else self.history.drop("S&P500", axis=1).set_index("Date")
        hist = remove_txn_hist(hist, txn_history)
        temp_txn = txn.copy()
        ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
        ref_hist = remove_txn_hist(ref_hist, ref_txn_hist)
        conversion_rate = get_current_conversion_rate(company["currency"], self.currency, cache)
        c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
        self.remove_txn_from_positions(c_div, txn, txn_history)
        self.stats = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                      "years_of_growth": 0}
        for temp_txn in self.transactions:
            conversion_rate = get_current_conversion_rate(company["currency"], self.currency, cache)
            c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
            self.add_txn_to_stats(c_div, company, temp_txn)
        hist["S&P500"] = ref_hist["Close"]
        self.history = hist
        self.compute_stats(hist)

    def compute_stats(self, hist):
        is_empty = len(self.transactions) == 0
        self.total = hist["Amount"].values[-1] if not is_empty else 0
        diff_price = (
                hist["Close"].values.flatten() - hist["Amount"].values.flatten()).tolist() if not is_empty else None
        self.stats["div_yield"] = self.stats["div_rate"] / self.total if not is_empty else 0
        self.stats["net_div_yield"] = self.stats["net_div_rate"] / self.total if not is_empty else 0
        self.stats["payout_ratio"] = self.stats["payout_ratio"] / self.total if not is_empty else 0
        self.stats["cagr1"] = cagr(self.stats["cagr1"], self.stats["div_rate"],
                                   1) if not is_empty else 0
        self.stats["cagr3"] = cagr(self.stats["cagr3"], self.stats["div_rate"],
                                   3) if not is_empty else 0
        self.stats["cagr5"] = cagr(self.stats["cagr5"], self.stats["div_rate"],
                                   5) if not is_empty else 0
        self.stats["years_of_growth"] = self.stats["years_of_growth"] / self.total if not is_empty else 0
        if self.history.empty:
            self.history = hist
        else:
            temp_merge = hist.combine_first(self.history)
            self.history = temp_merge
        self.current = self.total + diff_price[-1] if not is_empty else 0

    def add_txn_to_stats(self, c_div, company, txn):
        self.stats["div_rate"] += c_div
        self.stats["net_div_rate"] += get_net_dividend(c_div, company["country"])
        self.stats["cagr1"] += c_div * ((1 + company["cagr_1"]) ** 1)
        self.stats["cagr3"] += c_div * ((1 + company["cagr_3"]) ** 3)
        self.stats["cagr5"] += c_div * ((1 + company["cagr_5"]) ** 5)
        self.stats["payout_ratio"] += company["payout_ratio"] * txn["total"]
        self.stats["years_of_growth"] += company["continuous_dividend_growth"] * txn["total"]

    def to_dict(self):
        return {"_id": self.id, "email": self.user, "name": self.name, "transactions": self.transactions,
                "total": self.total, "currency": self.currency, "current": self.current, "summary": self.positions,
                "stats": self.stats, "history": self.history, "last_update": self.last_update,
                "id_txn": self.index_transaction}

    def add_txn_to_positions(self, c_div, company, txn, txn_hist):
        if txn["ticker"] not in self.positions:
            self.positions[txn["ticker"]] = {"total": 0, "shares": 0, "dividends": 0, "daily_change": 0,
                                             "daily_change_perc": 0, "total_change": 0, "total_change_perc": 0,
                                             "previous_total": 0,
                                             "name": txn["name"], "sector": company["sector"],
                                             "industry": company["industry"],
                                             "country": company["country"], "currency": company["currency"]}
        self.positions[txn["ticker"]]["shares"] += txn["shares"]
        self.positions[txn["ticker"]]["price"] = txn_hist["Close"][-1]
        self.positions[txn["ticker"]]["dividends"] += c_div
        self.positions[txn["ticker"]]["total"] += txn["total"]
        previous_amount = (txn_hist["Close"][-2] if txn_hist.shape[0] > 1 else txn["total"])
        if (datetime.today() - txn_hist.index[-1]).days >= 1:
            self.positions[txn["ticker"]]["daily_change"] += 0
        else:
            self.positions[txn["ticker"]]["daily_change"] += txn_hist["Close"][-1] - previous_amount
        self.positions[txn["ticker"]]["previous_total"] += previous_amount
        self.positions[txn["ticker"]]["total_change"] += txn_hist["Close"][-1] - txn["total"]
        self.positions[txn["ticker"]]["ex_dividend_date"] = company["stats"]["ex-dividend_date"]
        div_freq = dict()
        for key, value in company["dividend_history"].items():
            year = datetime.strptime(key, "%b %d, %Y").year
            if year not in div_freq:
                div_freq[year] = 0
            div_freq[year] += 1
        div_freq = [(year, value) for year, value in div_freq.items()]
        div_freq = sorted(div_freq, key=lambda x: x[0], reverse=True)
        div_freq = [x[1] for x in div_freq]
        self.positions[txn["ticker"]]["dividend_frequency"] = round(np.mean(div_freq[1:5]))

    def remove_txn_from_positions(self, c_div, txn, txn_hist):
        if txn["ticker"] not in self.positions:
            raise NameError("Ticker" + txn["ticker"] + " not in summary")
        self.positions[txn["ticker"]]["shares"] -= txn["shares"]
        if self.positions[txn["ticker"]]["shares"] == 0:
            del self.positions[txn["ticker"]]
        else:
            self.positions[txn["ticker"]]["price"] -= txn_hist["Close"][-1]
            self.positions[txn["ticker"]]["dividends"] -= c_div
            self.positions[txn["ticker"]]["total"] -= txn["total"]
            previous_amount = (txn_hist["Close"][-2] if txn_hist.shape[0] > 1 else txn["total"])
            if (datetime.today() - txn_hist.index[-1]).days >= 1:
                self.positions[txn["ticker"]]["daily_change"] += 0
            else:
                self.positions[txn["ticker"]]["daily_change"] -= txn_hist["Close"][-1] - previous_amount
            self.positions[txn["ticker"]]["previous_total"] -= previous_amount
            self.positions[txn["ticker"]]["total_change"] -= txn_hist["Close"][-1] - txn["total"]


def get_net_dividend(dividend, country):
    if country == "USA" or country == "United States":
        return dividend * 0.85
    elif country == "France":
        return dividend * 0.7
    elif country == "Switzerland":
        return dividend * 0.65
    elif country == "Canada":
        return dividend * 0.75
    elif country == "Australia":
        return dividend * 0.70
    else:
        return dividend


def get_history(cache, ticker, date, shares, end_date=datetime.now()):
    hist = cache.get(ticker, date, end_date)
    is_all_nan = hist.isna().all().all()
    if not is_all_nan:
        hist = hist.drop(["Open", "High", "Low", "Volume", "Stock Splits"], axis=1)

        hist["Dividends"] *= shares
        hist["Close"] *= shares
    else:
        hist["Dividends"] = np.zeros(len(hist["Close"]))
    return hist


def get_reference_history(currency, cache, temp_txn):
    ref_txn = temp_txn.copy()
    ref_txn["ticker"] = "^GSPC"
    ref_txn["name"] = "S&P500"
    ref_txn["shares"] = 1
    ref_txn_hist = compute_history(cache, currency, ref_txn, "USD", "USA")
    if len(ref_txn_hist["Close"]) > 0:
        ref_txn["shares"] = ref_txn["total"] / ref_txn_hist["Close"].values[0]
    else:
        ref_txn["shares"] = 0
    ref_txn_hist["Close"] *= ref_txn["shares"]
    ref_txn_hist["Amount"] = ref_txn["total"]
    return ref_txn_hist


def get_currency_ticker(currency, target_currency):
    ticker = currency
    if currency != target_currency:
        ticker = currency + target_currency + '=X'
        if currency == "USD":
            ticker = target_currency + '=X'
    return ticker


def get_current_conversion_rate(currency, target_currency, cache):
    ticker = get_currency_ticker(currency, target_currency)
    if ticker != currency:
        return cache.get_last_day(ticker)["Close"]
    return 1


def get_currency_history(currency, target_currency, cache, start_date, end_date):
    ticker = get_currency_ticker(currency, target_currency)
    if ticker != currency:
        return cache.get(ticker, start_date, end_date)["Close"]
    base = datetime.today()
    date_list = [base - timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    currency = Series(data=[1] * len(date_list), index=date_list)
    return currency


def compute_history(cache, target_currency, txn, currency, country):
    start_date = datetime.strptime(txn["date"], "%Y-%m-%d")
    txn_hist = get_history(cache, txn["ticker"], start_date, txn["shares"])
    currency_hist = get_currency_history(currency, target_currency, cache, start_date, datetime.now())
    mask = (currency_hist.index >= np.min(txn_hist.index)) & (currency_hist.index <= datetime.now())
    currency_hist = currency_hist.loc[mask]
    txn_hist["Close"] = txn_hist["Close"].fillna(method='ffill').fillna(method='bfill')
    txn_hist["Amount"] = [txn["price"] * txn["shares"]] * len(txn_hist["Close"])
    txn_hist["Close"] = txn_hist["Close"].mul(currency_hist, fill_value=1)
    txn_hist["Dividends"] = txn_hist["Dividends"].mul(currency_hist, fill_value=1)
    txn_hist["Net_Dividends"] = txn_hist["Dividends"].apply(get_net_dividend, args=(country,))
    return txn_hist


def add_txn_hist(hist, txn_hist):
    if hist.empty:
        hist = txn_hist
    else:
        new_hist = txn_hist.join(hist, lsuffix='', rsuffix='_right', how="outer")
        new_hist = new_hist.astype(float)
        new_hist["Dividends"].fillna(value=0, inplace=True)
        new_hist["Net_Dividends"].fillna(value=0, inplace=True)
        new_hist = new_hist.interpolate(method='linear', axis=0).ffill()
        txn_hist = new_hist[["Close_right", "Dividends_right", "Amount_right", "Net_Dividends_right", ]].set_axis(
            ["Close", "Dividends", "Amount", "Net_Dividends"], axis=1, inplace=False)
        hist = new_hist[["Close", "Dividends", "Amount", "Net_Dividends"]].add(txn_hist, fill_value=0)
    return hist


def remove_txn_hist(hist, txn_hist):
    if hist.empty:
        hist = txn_hist
    else:
        new_hist = txn_hist.join(hist, lsuffix='', rsuffix='_right', how="outer")
        new_hist = new_hist.astype(float)
        new_hist["Dividends"].fillna(value=0, inplace=True)
        new_hist["Net_Dividends"].fillna(value=0, inplace=True)
        new_hist = new_hist.interpolate(method='linear', axis=0).ffill()
        txn_hist = new_hist[["Close_right", "Dividends_right", "Amount_right", "Net_Dividends_right", ]].set_axis(
            ["Close", "Dividends", "Amount", "Net_Dividends"], axis=1, inplace=False)
        hist = txn_hist.sub(new_hist[["Close", "Dividends", "Amount", "Net_Dividends"]], fill_value=0)
        hist = hist[(hist[['Close']] != 0).all(axis=1)]
    return hist


def cagr(previous, after, years):
    return (previous / after) ** (1 / years) - 1
