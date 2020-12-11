import os
import time
from functools import wraps
import pandas as pd
import pycountry
import ccy
from flask import Flask, session, render_template, redirect, url_for
from flask_pymongo import PyMongo, request
from src.brokers.degiro import Degiro
from src.cache.companies_cache import CompaniesCache, fetch_company_from_api
from src.currency import Currency
from src.displayer.company_displayer import display_company
from all_functions import print_companies_to_html
from cryptography.fernet import Fernet
from datetime import datetime
from src.displayer.portfolio.portfolio_displayer import get_portfolio_context
from src.portfolio.portfolio import Portfolio
from src.cache.local_history_cache import LocalHistoryCache
from src.cache.currencies import Currencies
from src.displayer.portfolio.portfolio_displayer import format_amount
from flask_simple_geoip import SimpleGeoIP
from difflib import SequenceMatcher
from src.user.degiro_user import DegiroUser
from src.user.user import User
from src.user.authenticator import AuthenticationException, AuthenticatorFactory
from src.user.registor import RegistrationException
from src.user.registor import RegistratorFactory
from rq import Queue
from worker import conn

print("Creating Worker")
worker_queue = Queue(connection=conn)
print("Creating flask")
app = Flask("Company Explorer")
app.secret_key = os.environ["MONGO_KEY"]
pymongo_connected = False
companies_cache = None
mongo = None
tickers = None
print("Creating Local history cache")
history_cache = LocalHistoryCache()
print("Creating currencies")
currencies = Currencies()
if 'MONGO_URI' in os.environ and not pymongo_connected:
    environment = os.environ['FLASK_DEBUG']
    app.config['MONGO_DBNAME'] = 'staging_finance' if os.environ['FLASK_DEBUG'] else 'finance'
    app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
    app.config["GEOIPIFY_API_KEY"] = os.environ['WHOIS_KEY']
    encryptor = Fernet(bytes(os.environ["MONGO_KEY"], 'utf-8'))
    print("Creating pymongo")
    mongo = PyMongo(app)
    print("Creating SimpleGeoIP")
    simple_geoip = SimpleGeoIP(app)
    pymongo_connected = True
    print("Creating CompaniesCache")
    companies_cache = CompaniesCache(mongo.db.cleaned_companies)
    tickers = pd.DataFrame.from_records(mongo.db.tickers.find())
print("Setup completed")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_user_connected():
            return redirect(url_for('login', error_login="You must be connected to access this page"))
        return f(*args, **kwargs)

    return decorated_function


def create_user_session(user):
    session["USER"] = str(user.id)
    session["FIRST_NAME"] = str(user.first_name)
    session["USER_TYPE"] = str(user.type)
    session.new = True


def is_user_connected():
    user_id = session.get("USER")
    if user_id and User.does_id_exist(mongo.db.users, user_id):
        return True
    elif user_id:
        session.clear()
    return False


# WARNING - ERASE ALL DATABASE - ONLY USE FOR CLEAN START ON STAGING
@app.route('/clean_start')
def clean_start():
    mongo.db.users.drop()
    mongo.db.portfolio.drop()
    session.clear()
    return redirect(url_for("login"))


@app.route('/')
def explore_companies():
    if is_user_connected():
        return display_portfolios_manager()
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


@app.route('/refresh_staging')
@login_required
def refresh_staging_prod():
    collections = mongo.db.client.finance.list_collection_names()
    for collection in collections:
        print("Collection: " + collection)
        documents = list(mongo.db.client.finance[collection].find())
        mongo.db.client.staging_finance[collection].drop()
        for index in range(0, len(documents), 100):
            if index + 100 < len(documents):
                mongo.db.client.staging_finance[collection].insert_many(documents[index:index + 100])
            else:
                mongo.db.client.staging_finance[collection].insert_many(documents[index:len(documents)])


@app.route('/screener/<ticker>')
def show_company(ticker):
    print("Displaying company: " + ticker)
    global companies_cache
    db_company = companies_cache.get(ticker)
    today = datetime.now()
    if companies_cache.should_update_company(ticker, today):
        print("update company: " + ticker)
        worker_queue.enqueue(fetch_company_from_api, ticker, companies_cache)
        #fetch_company_from_api(ticker, companies_cache)
    if db_company is not None:
        return display_company(db_company, ticker)
    return "No company found"


@app.route('/portfolios-manager', methods=['GET'])
@login_required
def show_portfolio_manager():
    return display_portfolios_manager()


@app.route('/portfolios-manager', methods=['POST'])
@login_required
def add_portfolio():
    data = request.form.to_dict(flat=True)
    portfolio = mongo.db.portfolio.find_one({"email": session["USER"], "name": data["name"]})
    if portfolio is not None:
        return display_portfolios_manager()
    portfolio = {"email": session["USER"], "name": data["name"], "transactions": [], "total": 0, "dividend_history": {},
                 "currency": data["currency"], "id_txn": 0, "history": {}, "current": 0,
                 "summary": {}, "stats": {}, "last_update": datetime.now()}
    mongo.db.portfolio.insert_one(portfolio)
    return redirect(url_for("show_portfolio", name=data["name"]))


def display_portfolios_manager():
    global currencies
    portfolios = list(mongo.db.portfolio.find({"email": session["USER"]}))
    is_portfolio = len(portfolios)
    for portfolio in portfolios:
        portfolio["total"] = format_amount(portfolio["total"], Currency(portfolio["currency"]))
        if "current" in portfolio:
            portfolio["current"] = format_amount(portfolio["current"], Currency(portfolio["currency"]))
        else:
            portfolio["current"] = portfolio["total"]
    keys = sorted(list(currencies.keys()))
    return render_template("portfolios_manager.html", portfolios=portfolios,
                           is_portfolio=is_portfolio,
                           currencies=keys)


@app.route('/portfolio', methods=['GET'])
@login_required
def show_portfolio():
    request_start = time.time()
    portfolio_name = request.args.get("name")
    portfolio = Portfolio.retrieve_from_database(mongo.db.portfolio, session["USER"], portfolio_name)
    print("Get portfolio --- %s seconds ---" % (time.time() - request_start))
    tab = "Summary"
    if portfolio is None:
        return redirect(url_for("show_portfolio_manager"))
    update_portfolio(portfolio)
    print("Update portfolio --- %s seconds ---" % (time.time() - request_start))
    context = get_portfolio_context(portfolio, tickers, tab)
    print("Get plots and graphs --- %s seconds ---" % (time.time() - request_start))
    context["user_id"] = session["USER"]
    print("Total request time --- %s seconds ---" % (time.time() - request_start))
    return render_template("portfolio.html", **context)


def update_portfolio(portfolio):
    companies_cache.update_from_transactions(portfolio.transactions)
    if 60 < (datetime.now() - portfolio.last_update).seconds < 24 * 60 * 60:
        history_cache.today_update_from_transactions(portfolio.transactions, companies_cache, portfolio.currency)
    else:
        history_cache.update_from_transactions(portfolio.transactions, companies_cache, portfolio.currency)
    portfolio.update(history_cache, companies_cache, mongo.db.portfolio)


@app.route('/portfolio', methods=['POST'])
@login_required
def handle_txn():
    portfolio_name = request.args.get("name")
    portfolio = Portfolio.retrieve_from_database(mongo.db.portfolio, session["USER"], portfolio_name)
    if portfolio is None:
        return redirect(url_for("show_portfolio_manager"))
    data = request.form.to_dict(flat=True)
    tab = "Summary"
    if data["action"] == "add_transaction":
        portfolio.add_transaction(data, history_cache, companies_cache)
        tab = "Transactions"
    elif data["action"] == "del":
        if "id" in data:
            portfolio.remove_transaction(data, history_cache, companies_cache)
    update_portfolio(portfolio)
    context = get_portfolio_context(portfolio, tickers, tab)
    context["user_id"] = session["USER"]
    return render_template("portfolio.html", **context)


@app.route('/login', methods=['GET'])
def show_login_form():
    print("login")
    if is_user_connected():
        return redirect(url_for("show_portfolio_manager"))
    data = request.args
    if "error_login" in data:
        return render_template("login.html", error_login=data["error_login"])
    return render_template("login.html")


@app.route('/login', methods=['POST'])
def login():
    global mongo
    if is_user_connected():
        return redirect(url_for("show_portfolio_manager"))
    data = request.form
    try:
        authenticator = AuthenticatorFactory.create(data["login_method"], encryptor, mongo.db.users)
        user = authenticator.authenticate(data)
        create_user_session(user)
        return redirect(url_for("show_portfolio_manager"))
    except AuthenticationException as err:
        return render_template("login.html", error_login=err)
    except Exception as err:
        raise err


@app.route('/logout')
def logout():
    if session.get("USER"):
        session.clear()
    return redirect(url_for("login"))


@app.route('/register', methods=['GET'])
def show_registration_form():
    if is_user_connected():
        return redirect(url_for("show_portfolio_manager"))
    return render_template("register.html")


@app.route('/register', methods=['POST'])
def register():
    global mongo
    if is_user_connected():
        return redirect(url_for("show_portfolio_manager"))
    data = request.form.to_dict(flat=True)
    try:
        registrator = RegistratorFactory.create(data["registration_method"], encryptor, mongo.db.users)
        user = registrator.register(data, simple_geoip)
        create_user_session(user)
        return redirect(url_for("show_portfolio_manager"))
    except RegistrationException as err:
        return render_template("login.html", error_login=err)


@app.route('/import_portfolio', methods=['GET'])
@login_required
def import_portfolio():
    start_time = time.time()
    user = DegiroUser.create_from_db(mongo.db.users, session["USER"], encryptor)
    degiro = Degiro(user=None, data=None, session_id=user.session_id, account_id=user.account_id)
    try:
        degiro.get_client_config()
        degiro.get_degiro_config()
        degiro.get_data()
    except ConnectionError as err:
        session.clear()
        return redirect(url_for('login', error_login="Session expired"))
    product_ids = [position["id"] for position in degiro.data["portfolio"]["value"] if position["id"].isdigit()]
    products = degiro.get_products_by_ids(product_ids)
    movements = degiro.get_account_overview("01/01/1970", datetime.now().strftime("%d/%m/%Y"))

    print("Degiro total request time --- %s seconds ---" % (time.time() - start_time))
    names = tickers["Name"].tolist()
    names = [str(name).lower() for name in names]
    modified_tickers = tickers["Ticker"].tolist()
    modified_tickers = [ticker.split('.')[0] for ticker in modified_tickers]
    for movement in movements:
        ticker = products[str(movement["productId"])]["symbol"]
        currency = products[str(movement["productId"])]["currency"]
        name = products[str(movement["productId"])]["name"].lower()
        indexes = [index for index in range(len(modified_tickers)) if modified_tickers[index] == ticker ]
        if len(indexes) > 0:
            for index in indexes:
                country = tickers["Country"][index]
                country = pycountry.countries.get(
                    name=country if country != "USA" else "United States")
                company_currency = ccy.countryccy(country.alpha_2)
                company_name = names[index]
                similarity_index = SequenceMatcher(None, name, company_name).ratio()
                if similarity_index > 0.5 and currency == company_currency:
                    movement["ticker"] = tickers["Ticker"].tolist()[index]
                    movement["name"] = tickers["Name"].tolist()[index]
        movement["date"] = movement["date"].strftime("%Y-%m-%d")
    portfolio = {"email": session["USER"], "name": "Degiro", "transactions": [], "total": 0, "dividend_history": {},
                 "currency": "EUR", "id_txn": 0, "history": {}, "current": 0,
                 "summary": {}, "stats": {}, "last_update": datetime.now()}
    mongo.db.portfolio.insert_one(portfolio)
    portfolio = Portfolio.retrieve_from_database(mongo.db.portfolio, session["USER"], "Degiro")
    companies_cache.update_from_transactions(movements)

    history_cache.update_from_transactions(movements, companies_cache, portfolio.currency)
    for movement in movements:
        portfolio.add_transaction(movement, history_cache, companies_cache)
    update_portfolio(portfolio)
    return redirect(url_for("show_portfolio_manager"))



if __name__ == '__main__':
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=False)
