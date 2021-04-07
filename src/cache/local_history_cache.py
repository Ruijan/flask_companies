import math
import os
import time
from datetime import datetime, timedelta
import yfinance as yf
import fmpsdk
from urllib.request import urlopen
import json
import pandas as pd
from src.currency import Currency

Y_M_D = "%Y-%m-%d"

FINANCE_KEY_ = os.environ["FINANCE_KEY"]


def get_range(end_date, period, start_date):
    if end_date is None:
        end_date = datetime.today()
    if start_date is None:
        if period == "max":
            start_date = datetime(1900, 1, 1)
        else:
            amount = int(period[0])
            element_of_time = period[1]
            if element_of_time == "d":
                start_date = end_date - timedelta(days=amount)
            elif element_of_time == "w":
                start_date = end_date - timedelta(weeks=amount)
            elif element_of_time == "m":
                start_date = end_date - timedelta(weeks=4 * amount)
            elif element_of_time == "y":
                start_date = end_date - timedelta(weeks=52 * amount)
    return end_date, start_date


def rearrange_data_in_dictionnary(data, tickers, end_date, list_tickers, start_date):
    all_prices = {}
    all_dividends = {}
    for ticker in tickers:
        currency_history = {(start_date + timedelta(days=x)).strftime(Y_M_D): math.nan for x in
                            range((end_date - start_date).days)}
        currency_div_history = {(start_date + timedelta(days=x)).strftime(Y_M_D): 0 for x in
                                range((end_date - start_date).days)}
        if ticker in list_tickers:
            for payment in data[list_tickers[ticker]]["historical"]:
                currency_history[payment["date"]] = payment["adjClose"]
        all_prices[ticker] = currency_history
        all_dividends[ticker] = currency_div_history
    return all_dividends, all_prices


class LocalHistoryCache(dict):
    __instance = None
    __source = "grep"

    @staticmethod
    def get_instance():
        if LocalHistoryCache.__instance is not None:
            return LocalHistoryCache.__instance
        else:
            return LocalHistoryCache()

    def __init__(self):
        super().__init__()
        if LocalHistoryCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            LocalHistoryCache.__instance = self

    def get_currency_ticker(self, currency1, currency2):
        if self.__source == "grep":
            return get_currency_ticker_grep(currency1, currency2)
        return get_currency_ticker_yahoo(currency1, currency2)

    def get_forex(self, currency1, currency2, start_date=None, end_date=None, period="max"):
        if self.__source == "grep":
            ticker = get_currency_ticker_grep(currency1, currency2)
        else:
            ticker = get_currency_ticker_yahoo(currency1, currency2)
        return self.get(ticker, start_date, end_date, period)

    def get_market_index_ticker(self, index_name):
        if self.__source == "grep":
            return index_name.replace("^", "%5E")
        return index_name

    def get(self, key, start_date=None, end_date=None, period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        self[key] = self.fetch_history(key, start_date, end_date, period)
        hist = self[key]["history"].copy()
        hist.index = pd.to_datetime(hist.index)
        mask = (hist.index >= start_date) & (hist.index <= end_date)
        return hist.loc[mask]

    def get_last_day(self, key):
        if key not in self:
            if self.__source != "grep":
                history = yf.Ticker(key).history(period="1d")
            else:
                history = fmpsdk.quote_short(apikey=os.environ["FINANCE_KEY"], symbol=key)

            self[key] = {"history": history,
                         "last_update": datetime.now(),
                         "start_date": datetime.today() - timedelta(days=1),
                         "end_date": datetime.today()}
            self[key]["history"] = self[key]["history"].loc[~self[key]["history"].index.duplicated(keep='first')]
        last_day_close = self[key]["history"].loc[self[key]["history"].index.max(), :]
        return last_day_close

    def fetch_history(self, key, start_date=None, end_date=None, period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        temp_data = None
        if key not in self.keys():
            start = time.time()
            temp_data = {"history": yf.Ticker(key).history(start=start_date, end=end_date),
                         "last_update": datetime.now(),
                         "start_date": start_date,
                         "end_date": end_date}
            print("GET COMPANY HISTORY %s seconds ---" % (time.time() - start))
        elif key in self:
            temp_data = self[key].copy()
            diff_time = self[key]["start_date"] - start_date
            if diff_time.days > 0:
                added_history = yf.Ticker(key).history(start=start_date,
                                                       end=self[key]["start_date"] - timedelta(days=1))
                temp_data["history"].index = pd.to_datetime(temp_data["history"].index)
                temp_data["history"] = temp_data["history"].append(added_history).sort_values(by=["Date"],
                                                                                              ascending=True)

                temp_data["start_date"] = start_date
        temp_data["history"]["Close"] = temp_data["history"]["Close"].fillna(method='ffill').fillna(method='bfill')
        temp_data["history"] = temp_data["history"].loc[~temp_data["history"].index.duplicated(keep='first')]
        return temp_data

    def fetch_multiple_histories(self, keys, currency_tickers, index_tickers, start_date=None, end_date=None,
                                 period="max"):
        end_date, start_date = get_range(end_date, period, start_date)
        ticker_to_download = [key for key in keys if key not in self]
        currency_to_download = [key for key in currency_tickers if key not in self]
        index_to_download = [key for key in index_tickers if key not in self]
        keys_in_cache = [key for key in keys + currency_tickers + index_tickers if key in self]
        results = {}
        if len(ticker_to_download + currency_to_download + index_to_download) > 0:

            if self.__source == "grep":
                data = self.fetch_history_multiple_ticker_grep(end_date, ticker_to_download, currency_to_download,
                                                               index_to_download, start_date)
            else:
                tickers = " ".join(ticker_to_download + currency_to_download + index_to_download)

                data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', auto_adjust=True,
                                   actions=True)
            data.index.name = "Date"
            for key in data.columns:
                if len(ticker_to_download + currency_to_download + index_to_download) > 1:
                    temp_data = data[key[0]]
                else:
                    temp_data = data
                temp_data = temp_data.fillna(method='ffill')
                temp_data = temp_data.fillna(method='bfill')
                temp_data = temp_data.loc[~temp_data.index.duplicated(keep='first')]
                results[key[0]] = {"history": temp_data,
                                   "last_update": datetime.now(),
                                   "start_date": start_date,
                                   "end_date": end_date}
        for key in keys_in_cache:
            results[key] = self[key]
        return results

    def fetch_history_multiple_ticker_grep(self, end_date, stock_keys, currency_tickers, index_tickers, start_date):
        today = datetime.today()
        today = today.replace(hour=0, minute=0, second=0, microsecond=0)
        formatted_index_tickers = [stock_key.replace("^", "%5E") for stock_key in index_tickers]

        # Retrieve Index market
        all_indices_div, all_indices_price = self.retrieve_index(end_date, formatted_index_tickers, index_tickers,
                                                                 start_date)

        # Retrieve currencies
        all_currencies_div, all_currencies_price = self.retrieve_currencies(currency_tickers, end_date, start_date)

        # Retrieve dividends
        all_dividends = self.extract_dividends(end_date, start_date, stock_keys)
        all_dividends.update(all_currencies_div)
        all_dividends.update(all_indices_div)
        data = None
        # Retrieve price
        if (end_date - start_date).days > 1:
            prices = retrieve_data_five_by_five(stock_keys, fmpsdk.historical_price_full, series_type="line",
                                                from_date=start_date.strftime(Y_M_D),
                                                to_date=end_date.strftime(Y_M_D))
            list_prices = {prices[index]["symbol"]: index for index in range(len(prices)) if prices[index]}

            all_prices = {}
            for stock_name in stock_keys:
                price_history = {(start_date + timedelta(days=x)).strftime(Y_M_D): math.nan for x in
                                 range((end_date - start_date).days)}
                if stock_name in list_prices:
                    for payment in prices[list_prices[stock_name]]["historical"]:
                        price_history[payment["date"]] = payment["close"]
                all_prices[stock_name] = price_history
            all_prices.update(all_currencies_price)
            all_prices.update(all_indices_price)
            for company in all_prices.keys():
                header = pd.MultiIndex.from_product([[company], ["Close"]], names=['Ticker', 'Parameters'])
                header2 = pd.MultiIndex.from_product([[company], ["Dividends"]],
                                                     names=['Ticker', 'Parameters'])

                df = pd.DataFrame(all_prices[company].values(), index=all_prices[company].keys(), columns=header)
                df2 = pd.DataFrame(all_dividends[company].values(), index=list(all_dividends[company].keys()),
                                   columns=header2)
                result = pd.concat([df, df2], axis=1, sort=False)
                result = result.fillna(method='ffill')
                result = result.fillna(method='bfill')
                data = result if data is None else pd.concat([data, result], axis=1, sort=False)

        else:
            all_prices = fmpsdk.quote_short(apikey=FINANCE_KEY_, symbol=','.join(stock_keys))
            all_prices += fmpsdk.quote_short(apikey=FINANCE_KEY_, symbol=','.join(formatted_index_tickers))
            data2 = fmpsdk.forex(apikey=FINANCE_KEY_)
            for fx in data2:

                currencies = fx["ticker"].split("/")
                try:
                    first_currency_combi = self.get_currency_ticker(Currency(currencies[0]), Currency(currencies[1]))
                    second_currency_combi = self.get_currency_ticker(Currency(currencies[1]), Currency(currencies[0]))
                    if first_currency_combi in currency_tickers:
                        all_prices += [{"symbol": first_currency_combi, "price": float(fx["ask"])}]
                    elif second_currency_combi in currency_tickers:
                        all_prices += [{"symbol": second_currency_combi, "price": 1/float(fx["ask"])}]
                except AttributeError:
                    pass

            for company in all_prices:
                symbol = company["symbol"]
                header = pd.MultiIndex.from_product([[symbol], ["Close"]], names=['Ticker', 'Parameters'])
                header2 = pd.MultiIndex.from_product([[symbol], ["Dividends"]], names=['Ticker', 'Parameters'])

                df = pd.DataFrame([company["price"]], index=[today.strftime(Y_M_D)], columns=header)
                df2 = pd.DataFrame(all_dividends[symbol].values(), index=list(all_dividends[symbol].keys()),
                                   columns=header2)
                result = pd.concat([df, df2], axis=1, sort=False)
                result = result.fillna(method='ffill')
                result = result.fillna(method='bfill')
                data = result if data is None else pd.concat([data, result], axis=1, sort=False)
        return data

    def retrieve_currencies(self, currency_tickers, end_date, start_date):
        currencies = retrieve_data_five_by_five(currency_tickers, fmpsdk.historical_price_full,
                                                from_date=start_date.strftime(Y_M_D), to_date=end_date.strftime(Y_M_D))
        list_currencies = {currencies[index]["symbol"].replace("/", ""): index for index in range(len(currencies)) if
                           currencies[index]}
        all_currencies_div, all_currencies_price = rearrange_data_in_dictionnary(currencies, currency_tickers,
                                                                                      end_date, list_currencies,
                                                                                      start_date)
        return all_currencies_div, all_currencies_price

    def retrieve_index(self, end_date, formatted_index_tickers, index_tickers, start_date):
        indices = retrieve_data_five_by_five(formatted_index_tickers, fmpsdk.historical_price_full,
                                             from_date=start_date.strftime(Y_M_D), to_date=end_date.strftime(Y_M_D))
        if not isinstance(indices, list):
            indices = [indices]
        list_indices = {indices[index]["symbol"]: index for index in range(len(indices)) if indices[index]}
        all_indices_div, all_indices_price = rearrange_data_in_dictionnary(indices, index_tickers, end_date,
                                                                                list_indices, start_date)
        return all_indices_div, all_indices_price

    def extract_dividends(self, end_date, start_date, stock_keys):
        dividends = retrieve_data_five_by_five(stock_keys, fmpsdk.historical_stock_dividend)
        list_dividends = {dividends[index]["symbol"]: index for index in range(len(dividends)) if dividends[index]}
        all_dividends = {}
        for stock_name in stock_keys:
            dividends_history = {(start_date + timedelta(days=x)).strftime(Y_M_D): 0 for x in
                                 range((end_date - start_date).days)}
            if stock_name in list_dividends:
                for payment in dividends[list_dividends[stock_name]]["historical"]:
                    if payment["recordDate"]:
                        dividends_history[payment["date"]] = payment["adjDividend"]
            all_dividends[stock_name] = dividends_history
        return all_dividends

    def update_history(self, key, new_value):
        if key in self:
            self[key].update(new_value)
        else:
            self[key] = new_value

    def today_update_from_transactions(self, transactions, company_cache, currency):
        tickers = []
        currency_tickers = []
        index_tickers = []
        for txn in transactions:
            if txn["ticker"] not in tickers:
                tickers.append(txn["ticker"])
            currency_ticker = self.get_currency_ticker(Currency(company_cache[txn["ticker"]]["currency"]), currency)
            if currency_ticker not in currency_tickers and len(currency_ticker) > 3:
                currency_tickers.append(currency_ticker)
        index_tickers.append("^GSPC")
        results = self.fetch_multiple_histories(tickers, currency_tickers, index_tickers, period="1d")
        for ticker in results.keys():
            self.update_history(ticker, results[ticker])

    def update_from_transactions(self, transactions, company_cache, currency):
        stock_symbols = {}
        index_symbols = {}
        currencies_symbols = {}
        now = datetime.now()
        min_date = now
        for txn in transactions:
            date = datetime.strptime(txn["date"], Y_M_D)
            currency_ticker = self.get_currency_ticker(Currency(company_cache[txn["ticker"]]["currency"]), currency)
            if currency_ticker:
                if currency_ticker not in currencies_symbols:
                    currencies_symbols[currency_ticker] = {"start": date, "end": now}
                if date < currencies_symbols[currency_ticker]["start"]:
                    currencies_symbols[currency_ticker]["start"] = date
            if txn["ticker"] not in stock_symbols:
                stock_symbols[txn["ticker"]] = {"start": date, "end": now}
            if date < stock_symbols[txn["ticker"]]["start"]:
                stock_symbols[txn["ticker"]]["start"] = date
            if date < min_date:
                min_date = date
        if len(stock_symbols) > 0:
            index_symbols["^GSPC"] = {"start": min_date, "end": now}
        results = self.fetch_multiple_histories(list(stock_symbols.keys()), list(currencies_symbols.keys()),
                                                list(index_symbols.keys()), min_date, now)
        for ticker in list(stock_symbols.keys()) + list(currencies_symbols.keys()) + list(index_symbols.keys()):
            self.update_history(ticker, results[ticker])


def get_currency_ticker_yahoo(currency, target_currency):
    ticker = ""
    if currency.short != target_currency.short:
        ticker = currency.short + target_currency.short + '=X'
        if currency == "USD":
            ticker = target_currency.short + '=X'
    return ticker


def get_currency_ticker_grep(currency, target_currency):
    if currency.short != target_currency.short:
        return currency.short + target_currency.short
    return ""


def get_json_parsed_data(url):
    response = urlopen(url)
    data = response.read().decode("utf-8")
    return json.loads(data)


def retrieve_data_five_by_five(tickers, method, **args):
    start_time = time.time()
    data = []
    for index in range(math.ceil(len(tickers) / 5)):
        current_keys = tickers[index * 5:((index + 1) * 5 if (index + 1) * 5 < len(tickers) else len(tickers))]
        temporary_data = method(apikey=os.environ["FINANCE_KEY"], symbol=','.join(current_keys), **args)
        data += temporary_data['historicalStockList'] if 'historicalStockList' in temporary_data else [temporary_data]
    print("Retrieving all data --- %s seconds ---" % (time.time() - start_time))
    return data



