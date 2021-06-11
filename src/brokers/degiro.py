import requests
import json
import getpass
from datetime import datetime, time, date
from collections import defaultdict
import numpy as np


def create_transaction(rmov, transactions, words, description):
    mov = dict()
    date = ''.join(rmov['date'].rsplit(':', 1))
    date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S%z')
    infos = description[1].split(' ')
    mov["shares"] = float(words[1])
    mov["price_COS"] = float(infos[0].replace(',', '.'))
    mov["price"] = mov["price_COS"]
    mov["total"] = abs(rmov["change"])
    c_transactions = [transaction for transaction in transactions if
                      "productId" in transaction and transaction["productId"] == rmov['productId'] and
                      transaction["date"] == rmov['date']]
    mov["fees"] = np.sum([abs(transaction['change']) for transaction in c_transactions if
                          "frais" in transaction["description"].lower() or "fees" in transaction[
                              "description"].lower()])

    if rmov['currency'] != "EUR":
        total = [transaction['change'] / transaction['exchangeRate'] for transaction in c_transactions if
                 rmov['currency'] == transaction["currency"] and transaction['type'] != "TRANSACTION"]
        if len(total) == 0:
            raise Exception("Bad transaction")
        mov["price"] = abs(total[0]) / mov["shares"]
        mov["total"] = abs(total[0])

    mov['date'] = date
    mov['change'] = rmov['change']
    mov['currency'] = rmov['currency']
    mov['description'] = rmov['description']
    mov['type'] = rmov['type']
    if 'orderId' in rmov:
        mov['orderId'] = rmov['orderId']
    if 'productId' in rmov:
        mov['productId'] = rmov['productId']
    return mov


class Degiro:
    def __init__(self, user=None, data=None, session=None, session_id=None, account_id=None):
        self.user = user if user is not None else dict()
        self.data = data
        self.session = session if session is not None else requests.Session()
        self.session_id = session_id
        self.account_id = account_id
        self.urls = {}

    def login(self, username, password, code, with2fa: bool = False):
        self.session = requests.Session()

        # Login
        url = 'https://trader.degiro.nl/login/secure/login'
        payload = {'username': username,
                   'password': password,
                   'isPassCodeReset': False,
                   'isRedirectToMobile': False}
        header = {'content-type': 'application/json'}
        if code is not None:
            payload['oneTimePassword'] = code
            url += '/totp'
        elif with2fa:
            payload['oneTimePassword'] = getpass.getpass("2FA Token: ")
            url += '/totp'
        r = self.session.post(url, headers=header, data=json.dumps(payload))
        if r.status_code == 6:
            raise ConnectionError('Requires two-factor identification')
        if r.status_code == 400:
            raise ConnectionError('Wrong password')
        # Get session id
        self.session_id = r.headers['Set-Cookie']
        self.session_id = self.session_id.split(';')[0]
        self.session_id = self.session_id.split('=')[1]
        self.get_client_config()
        self.get_degiro_config()

    def get_degiro_config(self):
        url = 'https://trader.degiro.nl/login/secure/config'
        payload = {'sessionId': self.session_id}
        r = self.session.get(url, params=payload)
        data = r.json()
        self.urls['paUrl'] = data['data']['paUrl']
        self.urls['reportingUrl'] = data['data']['reportingUrl']
        self.urls['productSearchUrl'] = data['data']['productSearchUrl']
        self.urls['productTypesUrl'] = data['data']['productTypesUrl']
        self.urls['reportingUrl'] = data['data']['reportingUrl']
        self.urls['tradingUrl'] = data['data']['tradingUrl']
        self.urls['vwdQuotecastServiceUrl'] = data['data']['vwdQuotecastServiceUrl']

    # This contain loads of user data, main interest here is the 'intAccount'
    def get_client_config(self):
        url = 'https://trader.degiro.nl/pa/secure/client'
        payload = {'sessionId': self.session_id}

        r = self.session.get(url, params=payload)
        print('Get config')
        print('\tStatus code: {}'.format(r.status_code))
        if r.status_code == 401:
            raise ConnectionError("Session expired")
        data = r.json()
        self.account_id = data['data']['intAccount']
        self.user = data['data']

        print('\tAccount id: {}'.format(self.account_id))

    # This gets a lot of data, orders, news, portfolio, cash funds etc.
    def get_data(self):
        url = 'https://trader.degiro.nl/trading/secure/v5/update/'
        url += str(self.account_id) + ';'
        url += 'jsessionid=' + self.session_id
        payload = {'portfolio': 0,
                   'totalPortfolio': 0,
                   'orders': 0,
                   'historicalOrders': 0,
                   'transactions': 0,
                   'alerts': 0,
                   'cashFunds': 0,
                   'intAccount': self.account_id,
                   'sessionId': self.session_id}

        r = self.session.get(url, params=payload)
        print('Get data')
        print('\tStatus code: {}'.format(r.status_code))

        self.data = r.json()

    # Get the cash funds
    def get_cash_funds(self):
        if self.data is None:
            self.get_data()
        cashFunds = dict()
        for cf in self.data['cashFunds']['value']:
            entry = dict()
            for y in cf['value']:
                # Useful if the currency code is the key to the dict
                if y['name'] == 'currencyCode':
                    key = y['value']
                    continue
                entry[y['name']] = y['value']
            cashFunds[key] = entry
        return cashFunds

    # Only returns a summary of the portfolio
    def get_portfolio_summary(self):
        pf = self.get_portfolio()
        cf = self.get_cash_funds()
        tot = 0
        for eq in pf['PRODUCT'].values():
            tot += eq['value']

        pfSummary = dict()
        pfSummary['equity'] = tot
        pfSummary['cash'] = cf['EUR']['value']
        return pfSummary

    # Returns the entire portfolio
    def get_portfolio(self):
        if self.data is None:
            self.get_data()
        portfolio = []
        for row in self.data['portfolio']['value']:
            entry = dict()
            for y in row['value']:
                k = y['name']
                v = None
                if 'value' in y:
                    v = y['value']
                entry[k] = v
            # Also historic equities are returned, let's omit them
            if entry['size'] != 0:
                portfolio.append(entry)

        ## Restructure portfolio and add extra data
        portf_n = defaultdict(dict)
        # Restructuring
        for r in portfolio:
            pos_type = r['positionType']
            pid = r['id']  # Product ID
            del (r['positionType'])
            del (r['id'])
            portf_n[pos_type][pid] = r

        # Adding extra data
        url = 'https://trader.degiro.nl/product_search/secure/v5/products/info'
        params = {'intAccount': str(self.account_id),
                  'sessionId': self.session_id}
        header = {'content-type': 'application/json'}
        pid_list = list(portf_n['PRODUCT'].keys())
        r = self.session.post(url, headers=header, params=params, data=json.dumps(pid_list))
        print('\tGetting extra data')
        print('\t\tStatus code: {}'.format(r.status_code))

        for k, v in r.json()['data'].items():
            del (v['id'])
            # Some bonds tend to have a non-unit size
            portf_n['PRODUCT'][k]['size'] *= v['contractSize']
            portf_n['PRODUCT'][k].update(v)

        return portf_n

    # Returns all account transactions
    #  fromDate and toDate are strings in the format: dd/mm/yyyy
    def get_account_overview(self, fromDate, toDate):
        url = 'https://trader.degiro.nl/reporting/secure/v4/accountoverview'
        payload = {'fromDate': fromDate,
                   'toDate': toDate,
                   'intAccount': self.account_id,
                   'sessionId': self.session_id}

        r = self.session.get(url, params=payload)
        print('Get account overview')
        print('\tStatus code: {}'.format(r.status_code))

        data = r.json()
        movs = []
        transactions = data['data']['cashMovements']
        for index in range(len(transactions)):
            rmov = transactions[index]
            if rmov["type"] == "TRANSACTION":
                description = rmov['description'].split('@')
                words = description[0].split(' ')
                if not words[1].isnumeric() or rmov["change"] < 0:
                    try:
                        mov = create_transaction(rmov, transactions, words, description)
                        movs.append(mov)
                    except Exception as e:
                        pass

        return movs

    def get_products_by_ids(self, ids):
        url = self.urls["productSearchUrl"] + "v5/products/info?intAccount=" + str(
            self.account_id) + "&sessionId=" + str(self.session_id)
        payload = json.dumps(ids)
        headers = {'Content-Type': 'application/json'}
        r = requests.post(url, headers=headers, data=payload)
        data = r.json()
        return data["data"]
