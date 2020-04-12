import os
import time

import pandas as pd
from flask import Flask, session, render_template, redirect, url_for
from flask_pymongo import PyMongo, request
from src.cache.companies_cache import CompaniesCache
from src.displayer.company_displayer import display_company
from all_functions import print_companies_to_html
from cryptography.fernet import Fernet
from datetime import datetime
from src.displayer.portfolio.portfolio_displayer import render_portfolio, compute_history, update_companies_cache, \
    add_txn_hist, get_reference_history, get_current_conversion_rate, add_txn_to_portfolio_summary, \
    add_txn_to_portfolio_stats, \
    postprocess_portfolio, remove_txn_from_portfolio_summary, remove_txn_hist
from src.cache.local_history_cache import LocalHistoryCache
from src.cache.currencies import Currencies
from src.displayer.portfolio.portfolio_displayer import format_amount
from flask_simple_geoip import SimpleGeoIP

app = Flask("Company Explorer")
app.secret_key = os.environ["MONGO_KEY"]
global pymongo_connected
global companies_cache
global mongo
global tickers
global history_cache
global currencies

pymongo_connected = False
if 'MONGO_URI' in os.environ and not pymongo_connected:
    app.config['MONGO_DBNAME'] = 'finance'
    app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
    app.config["GEOIPIFY_API_KEY"] = os.environ['WHOIS_KEY']
    mongo = PyMongo(app)
    simple_geoip = SimpleGeoIP(app)
    pymongo_connected = True
    companies_cache = CompaniesCache(mongo.db.cleaned_companies)
    history_cache = LocalHistoryCache(mongo.db.history)
    tickers = pd.DataFrame.from_records(mongo.db.tickers.find())
    currencies = Currencies()


def is_user_connected():
    if session.get("USER") and mongo.db.users.find_one({"email": session["USER"]}) is not None:
        return True
    elif session.get("USER"):
        session.clear()
    return False


@app.route('/')
def explore_companies():
    if is_user_connected():
        global pymongo_connected
        html = "Database not connected"
        current_country = request.args.get("country")
        if current_country is None:
            current_country = "All"
        if pymongo_connected:
            global companies_cache
            df = companies_cache.copy()
            df.reset_index(inplace=True)
            df = pd.concat([df, pd.DataFrame(list(df["stats"]))], axis=1, sort=False)
            if current_country != "All":
                df = df[df.country == current_country]
            df.set_index("ticker", inplace=True)
            html = print_companies_to_html(df)
        return render_template("companies.html", selected_country=current_country,
                               countries=companies_cache.country.unique(),
                               dividends=html)
    else:
        return redirect(url_for("login"))


@app.route('/screener/<ticker>')
def show_company(ticker):
    global companies_cache
    db_company = companies_cache.get(ticker)
    if db_company is not None:
        return display_company(db_company, ticker)
    return "No company found"


@app.route('/portfolios-manager', methods=['GET', 'POST'])
def show_portfolio_manager():
    if is_user_connected():
        if request.method == 'POST':
            data = request.form.to_dict(flat=True)
            portfolio = mongo.db.portfolio.find_one({"email": session["USER"], "name": data["name"]})
            if portfolio is None:
                portfolio = {"email": session["USER"], "name": data["name"], "transactions": [], "total": 0,
                             "currency": data["currency"], "invested": 0, "id_txn": 0, "history": {}, "current": 0,
                             "summary": {}, "stats": {}}
                mongo.db.portfolio.insert_one(portfolio)
                return redirect(url_for("show_portfolio", name=data["name"]))
            else:
                return display_portfolios_manager()
        else:
            return display_portfolios_manager()
    else:
        return redirect(url_for("login"))


def display_portfolios_manager():
    global currencies
    portfolios = list(mongo.db.portfolio.find({"email": session["USER"]}))
    is_portfolio = len(portfolios)
    for portfolio in portfolios:
        portfolio["total"] = format_amount(portfolio["total"], portfolio["currency"])
        if "current" in portfolio:
            portfolio["current"] = format_amount(portfolio["current"], portfolio["currency"])
        else:
            portfolio["current"] = portfolio["total"]
    keys = sorted(list(currencies.keys()))
    return render_template("portfolios_manager.html", portfolios=portfolios,
                           is_portfolio=is_portfolio,
                           currencies=keys)


@app.route('/portfolio', methods=['GET', 'POST'])
def show_portfolio():
    request_start = time.time()
    global companies_cache
    global mongo
    global tickers
    global history_cache
    if is_user_connected():
        portfolio_name = request.args.get("name")
        portfolio = mongo.db.portfolio.find_one({"email": session["USER"], "name": portfolio_name})
        tab = "Summary"
        if portfolio is None:
            return redirect(url_for("show_portfolio_manager"))
        if request.method == 'POST':
            data = request.form.to_dict(flat=True)
            if data["action"] == "add_transaction":
                add_transaction(data, portfolio, history_cache, companies_cache, mongo.db.portfolio)
                tab = "Transactions"
            elif data["action"] == "del":
                if "id" in data:
                    remove_transaction(data, portfolio, history_cache, companies_cache, mongo.db.portfolio)
        element = render_portfolio(portfolio, tickers, companies_cache, history_cache, tab, mongo.db.portfolio)
        print("Total request time --- %s seconds ---" % (time.time() - request_start))
        return element
    else:
        print("Total request time --- %s seconds ---" % (time.time() - request_start))
        return redirect(url_for("login"))


def add_transaction(data, portfolio, cache, companies_cache, db_portfolio):
    portfolio["id_txn"] += 1
    data["id"] = portfolio["id_txn"]
    data["shares"] = int(data["shares"])
    data["price_COS"] = float(data["price_COS"])
    data["price"] = float(data["price"])
    data["fees"] = float(data["fees"])
    data["total"] = data["price"] * data["shares"]
    data.pop("action")
    portfolio["transactions"].append(data)
    portfolio["total"] += data["total"]
    company = companies_cache.get(data["ticker"])
    update_companies_cache(companies_cache, portfolio)
    txn_history = compute_history(cache, portfolio["currency"], data, company["currency"], company["country"])
    ref_hist = pd.DataFrame() if not portfolio["history"] else pd.DataFrame.from_dict(portfolio["history"])[["S&P500","Date", "Amount", "Net_Dividends", "Dividends"]]
    if not ref_hist.empty:
        ref_hist = ref_hist.rename(columns={"S&P500": "Close"}).set_index("Date")
    hist = pd.DataFrame() if not portfolio["history"] else pd.DataFrame.from_dict(portfolio["history"]).drop("S&P500", axis=1).set_index("Date")
    if "history" not in portfolio:
        portfolio["history"] = pd.DataFrame()
    else:
        portfolio["history"] = pd.DataFrame.from_dict(portfolio["history"])
        if len(portfolio["history"]) > 0:
            portfolio["history"] = portfolio["history"].set_index("Date")
    if "summary" not in portfolio:
        portfolio["summary"] = dict()
    hist = add_txn_hist(hist, txn_history)
    temp_txn = data.copy()
    ref_txn_hist = get_reference_history(cache, portfolio, temp_txn)
    ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
    conversion_rate = get_current_conversion_rate(company["currency"], portfolio["currency"], cache)
    c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
    add_txn_to_portfolio_summary(c_div, company, portfolio["summary"], data, txn_history)
    portfolio["stats"] = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                          "years_of_growth": 0}
    for txn in portfolio["transactions"]:
        conversion_rate = get_current_conversion_rate(company["currency"], portfolio["currency"], cache)
        c_div = company["stats"]["forward_annual_dividend_rate"] * txn["shares"] * conversion_rate
        add_txn_to_portfolio_stats(c_div, company, portfolio["stats"], txn)
    for ticker, position in portfolio["summary"].items():
        position["total_change_perc"] = position["total_change"] / position["total"] * 100
        position["daily_change_perc"] = position["daily_change"] / position["previous_total"] * 100
        position["current_price"] = cache.get_last_day(ticker)["Close"]
    if portfolio["transactions"]:
        hist["S&P500"] = ref_hist["Close"]
    postprocess_portfolio(db_portfolio, hist, not portfolio["transactions"], portfolio)


def remove_transaction(data, portfolio, cache, companies_cache, db_portfolio):
    index = [index for index in range(len(portfolio["transactions"]))
             if portfolio["transactions"][index]["id"] == int(data["id"])]
    txn = portfolio["transactions"].pop(index[0])
    portfolio["total"] -= txn["total"]
    company = companies_cache.get(txn["ticker"])
    update_companies_cache(companies_cache, portfolio)
    txn_history = compute_history(cache, portfolio["currency"], txn, company["currency"], company["country"])
    ref_hist = pd.DataFrame() if not portfolio["history"] else pd.DataFrame.from_dict(portfolio["history"])[["S&P500","Date", "Amount", "Net_Dividends", "Dividends"]]
    if not ref_hist.empty:
        ref_hist = ref_hist.rename(columns={"S&P500": "Close"}).set_index("Date")
    hist = pd.DataFrame() if not portfolio["history"] else pd.DataFrame.from_dict(portfolio["history"]).drop("S&P500", axis=1).set_index("Date")
    if "history" not in portfolio:
        portfolio["history"] = pd.DataFrame()
    else:
        portfolio["history"] = pd.DataFrame.from_dict(portfolio["history"])
        if len(portfolio["history"]) > 0:
            portfolio["history"] = portfolio["history"].set_index("Date")
    if "summary" not in portfolio:
        portfolio["summary"] = dict()
    hist = remove_txn_hist(hist, txn_history)
    temp_txn = txn.copy()
    ref_txn_hist = get_reference_history(cache, portfolio, temp_txn)
    ref_hist = remove_txn_hist(ref_hist, ref_txn_hist)
    conversion_rate = get_current_conversion_rate(company["currency"], portfolio["currency"], cache)
    c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
    remove_txn_from_portfolio_summary(c_div, portfolio["summary"], txn, txn_history)
    portfolio["stats"] = {"div_rate": 0, "net_div_rate": 0, "cagr1": 0, "cagr3": 0, "cagr5": 0, "payout_ratio": 0,
                          "years_of_growth": 0}
    for temp_txn in portfolio["transactions"]:
        conversion_rate = get_current_conversion_rate(company["currency"], portfolio["currency"], cache)
        c_div = company["stats"]["forward_annual_dividend_rate"] * temp_txn["shares"] * conversion_rate
        add_txn_to_portfolio_stats(c_div, company, portfolio["stats"], temp_txn)
    hist["S&P500"] = ref_hist["Close"]
    portfolio["history"] = hist
    postprocess_portfolio(db_portfolio, hist, not portfolio["transactions"], portfolio)


@app.route('/login', methods=['GET', 'POST'])
def login():
    global mongo
    if is_user_connected():
        return redirect(url_for("show_portfolio"))
    if request.method == 'GET':
        return render_template("login.html")
    if request.method == 'POST':
        data = request.form
        f = Fernet(bytes(os.environ["MONGO_KEY"], 'utf-8'))
        users = list(mongo.db.users.find())
        user = None
        for tmp_user in users:
            if isinstance(tmp_user["email"], bytes):
                email = f.decrypt(tmp_user["email"]).decode("utf-8")
                if email == data["email"]:
                    user = tmp_user
            elif tmp_user["email"] == data["email"]:
                user = tmp_user
                user["first_name"] = f.encrypt(user["first_name"].encode())
                user["last_name"] = f.encrypt(user["last_name"].encode())
                user["email"] = f.encrypt(user["email"].encode())
                mongo.db.users.find_one_and_replace({"email": data["email"]}, user)
                portfolios = list(mongo.db.portfolio.find({"email": data["email"]}))
                for portfolio in portfolios:
                    portfolio["email"] = user["email"]
                    mongo.db.portfolio.find_one_and_replace({"email": data["email"]}, portfolio)
        if user is not None:
            db_pass = f.decrypt(user["pass"]).decode("utf-8")
            if db_pass == data["pass"]:
                session["KEY"] = os.environ["MONGO_KEY"]
                session["USER"] = user["email"]
                session.new = True
                return redirect(url_for("show_portfolio"))
            else:
                return render_template("login.html", error_login="Wrong password")
        else:
            return render_template("login.html", error_login="No user found with username")


@app.route('/logout')
def logout():
    if session.get("USER"):
        data = mongo.db.users.find_one({"email": session["USER"]})
        if data is not None:
            data["connected"] = False
            data["last_connection"] = datetime.now()
        session.clear()
    return redirect(url_for("login"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    global mongo
    if is_user_connected():
        return redirect(url_for("show_portfolio"))
    if request.method == 'GET':
        return render_template("register.html")
    if request.method == 'POST':
        data = request.form.to_dict(flat=True)
        f = Fernet(bytes(os.environ["MONGO_KEY"], 'utf-8'))
        data["pass"] = f.encrypt(data["pass"].encode())
        data["first_name"] = f.encrypt(data["first_name"].encode())
        data["last_name"] = f.encrypt(data["last_name"].encode())
        data["email"] = f.encrypt(data["email"].encode())
        data["creation_date"] = datetime.now()
        data["geolocation"] = simple_geoip.get_geoip_data()
        data.pop("pass2")
        user = None
        try:
            user = mongo.db.users.find_one({"email": data["email"]})
        except:
            pass
        if user is None:
            data["connected"] = True
            data["last_connection"] = datetime.now()
            mongo.db.users.insert_one(data)
            session["KEY"] = os.environ["MONGO_KEY"]
            session["USER"] = data["email"]
            session.new = True
            return redirect(url_for("show_portfolio"))
        else:
            return render_template("login.html", error_login="Email already in database. Try signing in")


if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run()
