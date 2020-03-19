import os
import time

import pandas as pd
from flask import Flask, session, render_template, redirect, url_for
from flask_pymongo import PyMongo, request

from cache.companies_cache import CompaniesCache
from displayer.company_displayer import display_company
from all_functions import print_companies_to_html
from cryptography.fernet import Fernet
from datetime import datetime
from displayer.portfolio.portfolio_displayer import render_portfolio
from cache.local_history_cache import LocalHistoryCache

app = Flask("Company Explorer")
app.secret_key = os.environ["MONGO_KEY"]
global pymongo_connected
global companies_cache
global mongo
global tickers
global history_cache


pymongo_connected = False
if 'MONGO_URI' in os.environ:
    app.config['MONGO_DBNAME'] = 'finance'
    app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
    mongo = PyMongo(app)
    pymongo_connected = True
    companies_cache = CompaniesCache(mongo.db.cleaned_companies)
    history_cache = LocalHistoryCache(mongo.db.history)
    tickers = pd.DataFrame.from_records(mongo.db.tickers.find())
    # request_filter = {
    #    "error_stats": {"$eq": False},
    #    "country": "France"
    # }
    # temp_df = pd.DataFrame.from_records(collection.find(request_filter))
    # tickers = pd.DataFrame.from_records(mongo.db.tickers.find())
    # temp_df.columns = [c.replace(' ', '_').lower() for c in temp_df.columns]
    # df = pd.concat([df, pd.DataFrame(list(df.apply(compute_dividends, axis=1)))], axis=1, sort=False)
    # print(temp_df.columns)
    # temp_df = temp_df.set_index("ticker")
    # companies_cache = temp_df


def is_user_connected():
    if session.get("USER") and mongo.db.users.find_one({"email": session["USER"]}) is not None:
        return True
    elif session.get("USER"):
        session.clear()
    return False


@app.route('/')
def explore_companies():
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


@app.route('/screener/<ticker>')
def show_company(ticker):
    global companies_cache
    db_company = companies_cache.loc[ticker]
    if db_company is not None:
        return display_company(db_company, ticker)
    return "No company found"


@app.route('/portfolio', methods=['GET', 'POST'])
def show_portfolio():
    request_start = time.time()
    global companies_cache
    global mongo
    global tickers
    global history_cache
    if is_user_connected():
        portfolio = mongo.db.portfolio.find_one({"email": session["USER"]})
        if portfolio is None:
            portfolio = {"email": session["USER"], "name": "My Portfolio", "transactions": [], "total": 0,
                         "currency": "EUR", "invested": 0, "id_txn": 0}
            mongo.db.portfolio.insert_one(portfolio)
        if request.method == 'POST':
            data = request.form.to_dict(flat=True)
            if data["action"] == "add":
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
                mongo.db.portfolio.find_one_and_replace({"email": session["USER"]}, portfolio)
            elif data["action"] == "del":
                if "id" in data:
                    index = [index for index in range(len(portfolio["transactions"]))
                             if portfolio["transactions"][index]["id"] == int(data["id"])]
                    portfolio["total"] -= portfolio["transactions"][index[0]]["total"]
                    portfolio["transactions"].pop(index[0])
                mongo.db.portfolio.find_one_and_replace({"email": session["USER"]}, portfolio)
        element = render_portfolio(portfolio, tickers, companies_cache, history_cache)
        print("Total request time --- %s seconds ---" % (time.time() - request_start))
        return element
    else:
        print("Total request time --- %s seconds ---" % (time.time() - request_start))
        return redirect(url_for("login"))


@app.route('/login', methods=['GET', 'POST'])
def login():
    global mongo
    if session.get("USER"):
        return redirect(url_for("show_portfolio"))
    if request.method == 'GET':
        return render_template("login.html")
    if request.method == 'POST':
        data = request.form
        f = Fernet(bytes(os.environ["MONGO_KEY"], 'utf-8'))
        user = mongo.db.users.find_one({"email": data["email"]})
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
        data.pop("pass2")
        user = None
        try:
            user = mongo.db.users.find_one({"user": data["user"]})
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
