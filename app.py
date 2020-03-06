import os

import pandas as pd
from bokeh.embed import components
from bokeh.models import HoverTool
from bokeh.plotting import figure
from flask import Flask, render_template
from flask_pymongo import PyMongo, request

from all_functions import compute_dividends, print_companies_to_html, get_yearly_dvidends

app = Flask("Company Explorer")
global pymongo_connected
global cache_df
pymongo_connected = False
if 'MONGO_URI' in os.environ:
    app.config['MONGO_DBNAME'] = 'finance'
    app.config['MONGO_URI'] = os.environ['MONGO_URI'].strip("'").replace('test', app.config['MONGO_DBNAME'])
    mongo = PyMongo(app)
    pymongo_connected = True

    collection = mongo.db.cleaned_companies
    request_filter = {
        "Error_stats": {"$eq": False},
        "Stats.Trailing P/E": {"$not": {"$eq": "N/A"}},
        "Stats.Payout Ratio": {"$not": {"$eq": "N/A"}},
        "Stats.Forward Annual Dividend Rate": {"$not": {"$eq": "N/A"}}
    }
    df = pd.DataFrame.from_records(collection.find(request_filter))
    df.columns = [c.replace(' ', '_').lower() for c in df.columns]
    df = pd.concat([df, pd.DataFrame(list(df.apply(compute_dividends, axis=1)))], axis=1, sort=False)
    df = df.set_index("ticker")
    cache_df = df


@app.route('/')
def explore_companies():
    global pymongo_connected
    html = "Database not connected"
    if pymongo_connected:
        # Determine the selected feature
        current_country = request.args.get("country")
        if current_country is None:
            current_country = "All"
        global cache_df
        df = cache_df.copy()
        df.reset_index(inplace=True)
        df = pd.concat([df, pd.DataFrame(list(df["stats"]))], axis=1, sort=False)
        if current_country != "All":
            df = df[df.country == current_country]
        df.set_index("ticker", inplace=True)
        html = print_companies_to_html(df)
    return render_template("companies.html", dividends=html)


@app.route('/screener/<ticker>')
def show_company(ticker):
    global cache_df
    db_company = cache_df.loc[ticker]
    if db_company is not None:
        dividends = get_yearly_dvidends(db_company.dividend_history, db_company.stock_splits)
        dividends = {'Date': list(dividends.index), 'Dividends': dividends.values.flatten().tolist()}
        dividends["Date"].reverse()
        dividends["Dividends"].reverse()
        p = figure(title="Dividend History", sizing_mode='stretch_both', toolbar_location=None)
        p.add_tools(HoverTool(
            tooltips="@Date : @{Dividends}{%0.2f}",
            formatters={'Dividends': 'printf'},
            mode='vline'
        ))
        p.vbar(x="Date", top="Dividends", width=0.9, source=dividends)
        p.xgrid.grid_line_color = None
        p.y_range.start = 0
        p.background_fill_alpha = 0.
        p.border_fill_alpha = 0.
        p.outline_line_alpha = 0.
        p.xaxis.axis_line_color = "cornsilk"
        p.xaxis.major_label_text_color = "cornsilk"
        p.yaxis.axis_line_color = "cornsilk"
        p.yaxis.major_label_text_color = "cornsilk"
        script, div = components(p)
        return render_template("index.html",
                               name=db_company["name"],
                               ticker=ticker,
                               sector=db_company.sector,
                               script=script,
                               dividends=div,
                               div_score="{:20,.0f}".format(db_company["div_score"]*100),
                               div_yield="{:20,.2f}%".format(db_company["Div. Yield"]*100),
                               cagr3="{:20,.2f}%".format(db_company["CAGR_3"]*100),
                               cagr5="{:20,.2f}%".format(db_company["CAGR_5"]*100),
                               payout="{:20,.2f}%".format(db_company["Payout_ratio"]*100),
                               growth=db_company["Continous Dividend Growth"])
    return "No company found"


if __name__ == '__main__':
    app.run()
