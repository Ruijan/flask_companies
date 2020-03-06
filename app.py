from flask import Flask, render_template
from flask_pymongo import PyMongo
import os
import pandas as pd
import matplotlib.pyplot as plt
import mpld3
from mpld3 import plugins
from all_functions import compute_dividends, print_companies_to_html, get_yearly_dvidends

app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'finance'
app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
print(app.config['MONGO_URI'])
print(app.config['MONGO_DBNAME'])
mongo = PyMongo(app)
global cache_df
collection = mongo.db.cleaned_companies
request_filter = {
    "Error_stats": {"$eq": False},
    "Stats.Trailing P/E": {"$not": {"$eq": "N/A"}},
    "Stats.Payout Ratio": {"$not": {"$eq": "N/A"}},
    "Stats.Forward Annual Dividend Rate": {"$not": {"$eq": "N/A"}},
    "Country": "France"
        }
df = pd.DataFrame.from_records(collection.find(request_filter))
df.columns = [c.replace(' ', '_').lower() for c in df.columns]
df = pd.concat([df, pd.DataFrame(list(df.apply(compute_dividends, axis=1)))], axis=1, sort=False)
df = df.set_index("ticker")
cache_df = df
print(cache_df)

@app.route('/')
def explore_companies():
    global cache_df
    df = cache_df.copy()
    df.reset_index(inplace=True)
    df = pd.concat([df, pd.DataFrame(list(df["stats"]))], axis=1, sort=False)
    df.set_index("ticker", inplace=True)
    html = print_companies_to_html(df)
    print(df["Trailing P/E"].loc["LI.PA"])
    return render_template("companies.html", dividends=html)

@app.route('/<country>')
def explore_company_per_country(country):
    global cache_df
    df = cache_df.copy()
    df.reset_index(inplace=True)
    df = pd.concat([df, pd.DataFrame(list(df["stats"]))], axis=1, sort=False)
    df = df[df.country == country]
    df.set_index("ticker", inplace=True)
    print(df.columns)
    print(df["Trailing P/E"])
    html = print_companies_to_html(df)
    return render_template("companies.html", dividends=html)


@app.route('/screener/<ticker>')
def show_company(ticker):
    global cache_df
    db_company = cache_df.loc[ticker]
    if db_company is not None:
        dividends = get_yearly_dvidends(db_company.dividend_history, db_company.stock_splits)
        dividends = {'Date': list(dividends.index), 'Dividends': dividends.values.flatten().tolist()}
        print(dividends)
        dividends["Date"].reverse()
        dividends["Dividends"].reverse()
        

        fig, ax = plt.subplots()
        plt1 = ax.bar(dividends["Date"], dividends["Dividends"])
        ax.set_xlabel('Year')
        ax.set_ylabel('Amount')
        ax.set_title('Dividends', size=20)
    
        ax.grid(True)
        #labels = [str(dividends["Date"][index] + ": " + str(dividends["Dividends"][index]) for index in range(len(dividends["Date"]))]
        
        return render_template("index.html",
                               name=db_company["name"],
                               ticker=ticker, 
                               sector=db_company.sector, 
                               dividends=mpld3.fig_to_html(fig))
    return "No company found"


if __name__ == '__main__':
    app.run()

