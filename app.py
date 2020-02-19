from flask import Flask, render_template
from flask_pymongo import PyMongo
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mpld3
from mpld3 import plugins
import numpy as np
from datetime import datetime
import pymongo

app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'finance'
app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
print(app.config['MONGO_URI'])
print(app.config['MONGO_DBNAME'])
mongo = PyMongo(app)
cache_df = None

def get_yearly_dvidends(dividends, stock_splits):
  dividend_dates = [datetime.strptime(key, "%b %d, %Y") for key in dividends.keys()]
  dividend_values = list(dividends.values())
  if isinstance(stock_splits, dict):
    for key in stock_splits.keys():
      key_time = datetime.strptime(key, "%b %d, %Y")
      if stock_splits[key] > 0:
        dividend_values = [dividends[datetime.strftime(c_date, "%b %d, %Y")] / stock_splits[key] if c_date < key_time else dividends[datetime.strftime(c_date, "%b %d, %Y")] for c_date in dividend_dates ]

  temp_dividends = {'Date': list(dividend_dates), 'values': dividend_values}
  df = pd.DataFrame.from_dict(temp_dividends)
  df['year'] = list(map(lambda x: x.year, df["Date"]))
  df['year_month'] = list(map(lambda x: str(x.year) + "_" + str(x.month) , df["Date"]))
  df = df.drop_duplicates(subset=['year_month'])
  df = df.groupby('year').sum()
  return df

def get_continuous_dividend_payment(yearly_dividends):
  countYears = 0
  divdiff = (yearly_dividends.values[1:] - yearly_dividends.values[0:-1]) / yearly_dividends.values[0:-1] * 100
  datediff = (yearly_dividends.index[1:] - yearly_dividends.index[0:-1]) / yearly_dividends.index[0:-1] * 100
  divdiff = np.flip(divdiff.flatten())
  datediff = np.flip(datediff)
  if len(divdiff) > 0:
    divdiff = np.delete(divdiff, 0)
  valid = True
  for index in range(len(divdiff)):
    if divdiff[index] < 0 or datediff[index] > 1:
      valid = False
    if valid:
      countYears += 1
  return countYears

def get_CAGR(yearly_dividends, years):
  if datetime.now().year - 1 in yearly_dividends.index and datetime.now().year - 1 - years in yearly_dividends.index:
    return (np.power(yearly_dividends.loc[datetime.now().year - 1] /yearly_dividends.loc[datetime.now().year - 1 - years] ,1/(years)) -1).values[0]
  elif datetime.now().year - 2 in yearly_dividends.index and datetime.now().year - 2 - years in yearly_dividends.index:
    return (np.power(yearly_dividends.loc[datetime.now().year - 2] /yearly_dividends.loc[datetime.now().year - 2 - years] ,1/(years)) -1).values[0]
  return 0

def get_dividend_features(dividends, stock_splits, payout_ratio, current_yield):
  data = {"CAGR_1": 0, "CAGR_3": 0, "CAGR_5": 0, "CAGR_10": 0, "Continous Dividend Growth": 0, "Payout_ratio": payout_ratio, "Div. Yield": current_yield, "div_score": 0}
  if isinstance(dividends, dict):
    yearly_dividends = get_yearly_dvidends(dividends, stock_splits)
    data["CAGR_1"] = get_CAGR(yearly_dividends, 1)
    data["CAGR_3"] = get_CAGR(yearly_dividends, 3)
    data["CAGR_5"] = get_CAGR(yearly_dividends, 5)
    data["CAGR_10"] = get_CAGR(yearly_dividends, 10)
    data["Continous Dividend Growth"] = get_continuous_dividend_payment(yearly_dividends)
    data["div_score"] = rate_dividends(data)
  return data

def rate_dividends(data):
  score = 0
  max_score = 8
  CAGR = [data["CAGR_1"], data["CAGR_3"], data["CAGR_5"], data["CAGR_10"]]
  if data["Div. Yield"] > 0.02:
    score += 1
  if data["Div. Yield"] > 0.05:
    score += 1
  if np.std(CAGR) < 0.2 * np.mean(CAGR) and np.mean(CAGR) > 0:
    score += 1
  if data["CAGR_1"] > 0.03 and data["CAGR_3"] > 0.03 and data["CAGR_5"] > 0.03:
    score += 1
  if data["CAGR_1"] < 0 or data["CAGR_3"] < 0 or data["CAGR_5"] < 0:
    score -= 1
  if data["Continous Dividend Growth"] > 8:
    score += 1
  if data["Continous Dividend Growth"] > 16:
    score += 1
  if data["Payout_ratio"]  < 1:
    score += 1
  if data["Payout_ratio"]  < 0.8:
    score += 1
  return score / max_score

@app.route('/')
def hello():
    if cache_df is None:_
        collection = mongo.db.companies
        a = collection.find();
        df = pd.DataFrame(list(a))
        df_an = df[df["Forward Annual Dividend Rate"].notna()]
        df_an = df_an[df_an["Forward Annual Dividend Rate"].apply(lambda x: not isinstance(x,str))]
        df_an = df_an[df_an["Trailing P/E"].apply(lambda x: not isinstance(x,str))]
        df_an = df_an[df_an["Payout Ratio"].apply(lambda x: not isinstance(x,str))]
        df_an = df_an.reset_index()
        data = [get_dividend_features(df_an["Dividend History"].values[index], df_an["Stock Splits"].values[index], df_an["Payout Ratio"].values[index], df_an["Forward Annual Dividend Yield"].values[index]) for index in range(len(df_an))]
        df_an = pd.concat([df_an, pd.DataFrame(data)], axis=1)
        cache_df = df_an
    keys = ["Ticker", "Name", "Sector", "Country", "Trailing P/E", "Forward P/E", "PEG Ratio (5 yr expected)",  "CAGR_3", "CAGR_5", "div_score", "Payout Ratio", "Forward Annual Dividend Yield", "5 Year Average Dividend Yield", "Continous Dividend Growth"]
    html = cache_df.sort_values(by=['div_score', "Forward Annual Dividend Yield"], ascending=False)[keys].set_index('Ticker').head(50).to_html()
    return html


@app.route('/screener/<ticker>')
def show_company(ticker):
    collection = mongo.db.companies
    db_company = collection.find_one({"Ticker": ticker})
    print(db_company)
    if db_company is not None:
        dividends = {'Date': list(db_company["Dividend History"].keys()), 'Dividends': list(db_company["Dividend History"].values())}
        dividends["Date"].reverse()
        dividends["Dividends"].reverse()
        
        fig, ax = plt.subplots()
        plt1 = ax.bar(dividends["Date"], dividends["Dividends"])
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title('Dividends', size=20)
    
        ax.grid(True)
        labels = [dividends["Date"][index] + ": " + str(dividends["Dividends"][index]) for index in range(len(dividends["Date"]))]
        
        return render_template("index.html", \
                               name=db_company["Name"], \
                               ticker=db_company["Ticker"], \
                                   sector=db_company["Sector"], \
                                       dividends=mpld3.fig_to_html(fig))
    return "No company found"
    #return mpld3.fig_to_html(fig)


if __name__ == '__main__':
    app.run()

