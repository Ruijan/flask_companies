import copy

import ccy
from pandas import DataFrame, Series
from datetime import datetime, timedelta
import numpy as np
import pycountry

from src.currency import Currency
from src.portfolio.position import Position


class Portfolio:
    def __init__(self, name, user, stats, history, dividend_transactions, last_update, positions, currency, identifier,
                 total, current, transactions):
        if len(name) == 0:
            raise AttributeError("Name should be at least one character")
        if isinstance(currency, Currency) == 0:
            raise AttributeError("Currency should be a Currency not" + str(type(currency)))
        self.name = name
        self.user = user
        self.stats = stats if stats is not None else DataFrame()
        self.history = history if history is not None else DataFrame()
        self.dividend_transactions = dividend_transactions if dividend_transactions is not None else DataFrame()
        self.last_update = last_update if last_update is not None else datetime.now()
        self.positions = dict()
        for ticker, position in positions.items():
            self.positions[ticker] = Position.create_from_dict(position)
        for ticker, position in positions.items():
            position["currency"] = Currency(position["currency"])
        self.currency = currency
        self.id = identifier
        self.total = total if total is not None else 0
        self.current = current if current is not None else 0
        self.transactions = transactions if total is not None else []
        self.index_transaction = int(
            np.max([txn["id"] for txn in transactions])) if transactions is not None and len(
            transactions) > 0 else 0
        pass

    @staticmethod
    def retrieve_from_database(database, user_email, name):
        portfolio = database.find_one({"email": user_email, "name": name})
        portfolio["history"] = DataFrame.from_dict(portfolio["history"])
        if "history" in portfolio and not portfolio["history"].empty:
            if portfolio["history"].index.name != "Date":
                portfolio["history"].set_index("Date", inplace=True)
        portfolio["dividend_history"] = DataFrame.from_dict(portfolio["dividend_history"])
        if "dividend_history" in portfolio and not portfolio["dividend_history"].empty:
            if portfolio["dividend_history"].index.name != "Date":
                portfolio["dividend_history"].set_index("Date", inplace=True)
        return Portfolio(portfolio["name"], portfolio["email"], portfolio["stats"],
                         portfolio["history"] if "history" in portfolio else None,
                         portfolio["dividend_history"] if "dividend_history" in portfolio else None,
                         portfolio["last_update"], portfolio["summary"], Currency(portfolio["currency"]),
                         portfolio["_id"],
                         portfolio["total"], portfolio["current"], portfolio["transactions"])

    def update(self, cache, cache_companies, db_portfolio):
        now = datetime.now()
        if len(self.transactions) > 0:
            diff_time = (now - self.last_update)
            if 60 < diff_time.seconds and diff_time.days < 1 and now.weekday() < 5:
                self.process_portfolio(cache, cache_companies, refresh=True)
            else:
                self.process_portfolio(cache, cache_companies)
        online_portfolio = self.to_dict().copy()

        online_portfolio["last_update"] = now
        db_portfolio.find_one_and_replace({"email": self.user, "name": self.name}, online_portfolio)

    def process_portfolio(self, cache, cache_companies, refresh=False):
        hist = DataFrame()
        ref_hist = DataFrame()

        self.positions = dict()
        self.stats = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                      "years_of_growth": 0}
        self.dividend_transactions = DataFrame()
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
            country = pycountry.countries.get(
                name=company["country"] if company["country"] != "USA" else "United States")
            company["currency"] = ccy.countryccy(country.alpha_2)

            txn_hist = compute_history(cache, self.currency, temp_txn, Currency(company["currency"]),
                                       company["country"])
            dividends = txn_hist.loc[txn_hist["Dividends"] > 0, "Dividends"]
            name = [txn["ticker"]] * len(dividends)
            df = {"Date": dividends.index, "Dividends": dividends.values, "Tickers": name}
            dividends = DataFrame(df)
            dividends.set_index("Date", inplace=True)
            if self.dividend_transactions.empty:
                self.dividend_transactions = dividends
            else:
                self.dividend_transactions = self.dividend_transactions.append(dividends)
            hist = add_txn_hist(hist, txn_hist)
            ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
            ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
            conversion_rate = get_current_conversion_rate(Currency(company["currency"]), self.currency, cache)
            c_div = self.get_current_dividend(company, conversion_rate, temp_txn["shares"])
            self.add_txn_to_stats(c_div, company, temp_txn)
            self.add_txn_to_positions(c_div, company, temp_txn, txn_hist, cache)
        if self.transactions:
            hist["S&P500"] = ref_hist["Close"]
        self.compute_stats(hist, cache_companies, cache)

    def add_transaction(self, data, cache, companies_cache):
        self.index_transaction += 1
        transaction = dict()
        transaction["id"] = self.index_transaction
        transaction["shares"] = int(data["shares"])
        transaction["price_COS"] = float(data["price_COS"])
        transaction["price"] = float(data["price"])
        transaction["fees"] = float(data["fees"])
        transaction["total"] = data["price"] * data["shares"]
        transaction["date"] = data["date"]
        transaction["ticker"] = data["ticker"]
        transaction["name"] = data["name"]

        self.transactions.append(transaction)
        self.total += transaction["total"]
        company = companies_cache.get(transaction["ticker"])
        country = pycountry.countries.get(name=company["country"] if company["country"] != "USA" else "United States")
        company["currency"] = ccy.countryccy(country.alpha_2)
        txn_history = compute_history(cache, self.currency, transaction, Currency(company["currency"]),
                                      company["country"])
        ref_hist = DataFrame() if self.history.empty else self.history[
            ["S&P500", "Amount", "Net_Dividends", "Dividends"]]
        if not ref_hist.empty:
            ref_hist = ref_hist.rename(columns={"S&P500": "Close"})
        hist = DataFrame() if self.history.empty else self.history.drop("S&P500", axis=1)
        hist = add_txn_hist(hist, txn_history)
        temp_txn = transaction.copy()
        ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
        ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
        conversion_rate = get_current_conversion_rate(Currency(company["currency"]), self.currency, cache)
        c_div = self.get_current_dividend(company, conversion_rate, temp_txn["shares"])
        self.add_txn_to_positions(c_div, company, transaction, txn_history, cache)
        if self.transactions:
            hist["S&P500"] = ref_hist["Close"]
        self.compute_stats(hist, companies_cache, cache)

    def remove_transaction(self, data, cache, companies_cache):
        index = [index for index in range(len(self.transactions))
                 if self.transactions[index]["id"] == int(data["id"])]
        txn = self.transactions.pop(index[0])
        self.total -= txn["total"]
        company = companies_cache.get(txn["ticker"])
        txn_history = compute_history(cache, self.currency, txn, Currency(company["currency"]), company["country"])
        ref_hist = DataFrame() if self.history.empty else self.history[
            ["S&P500", "Amount", "Net_Dividends", "Dividends"]]
        if not ref_hist.empty:
            ref_hist = ref_hist.rename(columns={"S&P500": "Close"})
        hist = self.history if self.history.empty else self.history.drop("S&P500", axis=1)
        hist = remove_txn_hist(hist, txn_history)
        temp_txn = txn.copy()
        ref_txn_hist = get_reference_history(self.currency, cache, temp_txn)
        ref_hist = remove_txn_hist(ref_hist, ref_txn_hist)
        conversion_rate = get_current_conversion_rate(Currency(company["currency"]), self.currency, cache)
        c_div = self.get_current_dividend(company, conversion_rate, temp_txn["shares"])
        self.remove_txn_from_positions(c_div, txn, txn_history)
        hist["S&P500"] = ref_hist["Close"]
        self.history = hist
        self.compute_stats(hist, companies_cache, cache)

    def compute_stats(self, hist, cache_companies, cache):
        if self.history.empty:
            self.history = hist
        else:
            temp_merge = hist.combine_first(self.history).fillna(method='ffill')
            self.history = temp_merge
            self.history["DividendCumSum"] = self.history["Dividends"].cumsum().fillna(method='ffill')
        self.stats = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                      "years_of_growth": 0}
        for txn in self.transactions:
            company = cache_companies.get(txn["ticker"])
            conversion_rate = get_current_conversion_rate(Currency(company["currency"]), self.currency, cache)
            c_div = self.get_current_dividend(company, conversion_rate, txn["shares"])
            self.add_txn_to_stats(c_div, company, txn)
        is_empty = len(self.transactions) == 0
        self.total = self.history["Amount"].values[-1] if not is_empty else 0
        diff_price = (self.history["Close"].values.flatten() - self.history[
            "Amount"].values.flatten()).tolist() if not is_empty else None
        self.stats["div_yield"] = self.stats["div_rate"] / self.total if not is_empty else 0
        self.stats["net_div_yield"] = self.stats["net_div_rate"] / self.total if not is_empty else 0
        self.stats["payout_ratio"] = self.stats["payout_ratio"] / self.total if not is_empty else 0
        self.stats["cagr1"] = cagr(self.stats["cagr1"], self.stats["div_rate"], 1) if not is_empty else 0
        self.stats["cagr3"] = cagr(self.stats["cagr3"], self.stats["div_rate"], 3) if not is_empty else 0
        self.stats["cagr5"] = cagr(self.stats["cagr5"], self.stats["div_rate"], 5) if not is_empty else 0
        self.stats["years_of_growth"] = self.stats["years_of_growth"] / self.total if not is_empty else 0
        self.current = self.total + diff_price[-1] if not is_empty else 0

    @staticmethod
    def get_current_dividend(company, conversion_rate, shares):
        return company["profile"]["lastDiv"] * shares * conversion_rate

    def add_txn_to_stats(self, c_div, company, txn):
        self.stats["div_rate"] += c_div
        self.stats["net_div_rate"] += get_net_dividend(c_div, company["country"])
        self.stats["cagr1"] += c_div * ((1 + company["cagr_1"]) ** 1)
        self.stats["cagr3"] += c_div * ((1 + company["cagr_3"]) ** 3)
        self.stats["cagr5"] += c_div * ((1 + company["cagr_5"]) ** 5)
        self.stats["payout_ratio"] += company["payout_ratio"] * txn["total"]
        self.stats["years_of_growth"] += company["continuous_dividend_growth"] * txn["total"]

    def to_dict(self):
        positions = copy.deepcopy(self.positions)
        for ticker in positions.keys():
            positions[ticker] = positions[ticker].json_format()
        history = self.history.reset_index().to_dict(orient="list") if not self.history.empty else {}
        dividend_history = self.dividend_transactions.reset_index().to_dict(orient="list") if not self.dividend_transactions.empty else {}
        return {"_id": self.id, "email": self.user, "name": self.name, "transactions": self.transactions,
                "dividend_history": dividend_history,
                "total": self.total, "currency": self.currency.short, "current": self.current, "summary": positions,
                "stats": self.stats, "history": history, "last_update": self.last_update,
                "id_txn": self.index_transaction}

    def add_txn_to_positions(self, c_div, company, txn, txn_hist, cache):
        if txn["ticker"] not in self.positions:
            current_price = cache.get_last_day(txn["ticker"])["Close"]
            div_frequency = Position.compute_div_frequency(company["dividend_history"])
            self.positions[txn["ticker"]] = Position(txn["name"], company["sector"], company["industry"],
                                                     company["country"], Currency(company["currency"]),
                                                     company["stats"]["ex-dividend_date"], div_frequency, current_price)
        self.positions[txn["ticker"]].add_transaction(txn, txn_hist, c_div)

    def remove_txn_from_positions(self, c_div, txn, txn_hist):
        if txn["ticker"] not in self.positions:
            raise NameError("Ticker" + txn["ticker"] + " not in summary")
        self.positions[txn["ticker"]].subtract_transaction(txn, txn_hist, c_div)
        if self.positions[txn["ticker"]].is_empty:
            del self.positions[txn["ticker"]]


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
        hist = hist.drop(["Open", "High", "Low", "Volume", "Stock Splits"], axis=1, errors='ignore')

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
    ref_txn_hist = compute_history(cache, currency, ref_txn, Currency("USD"), "USA")
    if len(ref_txn_hist["Close"]) > 0:
        if ref_txn_hist["Close"].values[0] == 0:
            print("WHY IS IT ZERO???")
        ref_txn["shares"] = ref_txn["total"] / ref_txn_hist["Close"].values[0]
    else:
        ref_txn["shares"] = 0
    ref_txn_hist["Close"] *= ref_txn["shares"]
    ref_txn_hist["Amount"] = ref_txn["total"]
    return ref_txn_hist


def get_current_conversion_rate(currency, target_currency, cache):
    ticker = cache.get_currency_ticker(currency, target_currency)
    if target_currency.short != currency.short:
        return cache.get_last_day(ticker)["Close"]
    return 1


def get_currency_history(currency, target_currency, cache, start_date, end_date):
    if target_currency.short != currency.short:
        return cache.get_forex(currency, target_currency, start_date, end_date)["Close"]
    base = datetime.today()
    base = base.replace(hour=0, minute=0, second=0, microsecond=0)
    date_list = [base - timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    currency_hist = Series(data=[1] * len(date_list), index=date_list)
    return currency_hist


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
