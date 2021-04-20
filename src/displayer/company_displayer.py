from bokeh.embed import components
from bokeh.models import HoverTool
from bokeh.plotting import figure
from flask import render_template
from src.extractor.dividend_analyzer import get_yearly_dividends, get_dividend_features
from datetime import datetime
import json


def display_company(db_company, ticker, price_cache):
    company_data = get_company_data(db_company, ticker, price_cache)
    dividends_data = json.dumps(company_data["dividends_data"]["dividend"], indent=2)
    revenues_data = json.dumps(company_data["financial_data"]["revenue"], indent=2)
    earnings_data = json.dumps(company_data["financial_data"]["netIncome"], indent=2)
    debt_data = json.dumps(company_data["balance_sheet_data"], indent=2)
    return render_template("company.html",
                           name=company_data["name"],
                           image=company_data["image"],
                           price=company_data["price"],
                           ticker=company_data["ticker"],
                           sector=company_data["sector"],
                           description=company_data["description"],
                           hierarchical_dividends_data=dividends_data,
                           hierarchical_revenues_data=revenues_data,
                           hierarchical_earnings_data=earnings_data,
                           hierarchical_debt_data=debt_data,
                           dividend_features=company_data["dividend_features"],
                           last_update=company_data["last_update"])


def get_company_data(db_company, ticker, price_cache):
    price_data = price_cache.get(ticker, period="1y").to_dict()
    close_price = {"values": [{"value": price_data["Close"][date], "date": date.strftime("%Y-%m-%d")} for date in price_data["Close"]], 'key': 'Close Price'}
    assets = {"values": [{"date": statement["date"], "value": statement["totalStockholdersEquity"]} for statement in
                         db_company["balance_sheet"]], "key": "Equity"}
    debt = {"values": [{"date": statement["date"], "value": statement["totalDebt"]} for statement in
                       db_company["balance_sheet"]], "key": "Debt"}
    dividend_features = get_dividend_features(db_company["dividend_history"], db_company["stock_splits"],
                                              db_company["stats"]["payoutRatio"],
                                              db_company["stats"]["dividendYield"])
    dividends = {'Date': list(db_company["dividend_history"].keys()),
                 'Dividends': list(db_company["dividend_history"].values())}
    dividends = [{"date": dividends["Date"][index], "dividend": dividends["Dividends"][index]} for index in
                 range(len(dividends["Dividends"]))]
    features = {feature: "{:20,.2f}%".format(dividend_features[feature] * 100) for feature in
                         ["div_yield", "cagr_1", "cagr_3", "cagr_5", "payout_ratio"]}
    features["continuous_dividend_growth"] = str(dividend_features["continuous_dividend_growth"])
    features["div_score"] = "{:20,.0f}".format(dividend_features["div_score"] * 100)
    news = db_company["news"] if "news" in db_company else {}
    company_data = {"name": db_company["name"],
                    "ticker": ticker,
                    "image": db_company["profile"]["image"],
                    "price": db_company["profile"]["price"],
                    "news": news,
                    "sector": db_company["sector"],
                    "description": db_company["profile"]["description"],
                    "price_data": {"data": [close_price], "reference": "Close Price"},
                    "financial_data": get_yearly_hierarchical_data(db_company["finances"], ["revenue", "netIncome"],
                                                                   'sum'),
                    "balance_sheet_data": {"data": [assets, debt], "reference": "Equity"},
                    "dividends_data": get_yearly_hierarchical_data(dividends, ["dividend"], 'sum', unique=False),
                    "dividend_features": features,
                    "last_update": datetime.strftime(db_company["last_update"], "%Y-%m-%d")}
    return company_data


def get_yearly_hierarchical_data(data, variables, aggregation_method="sum", unique=True):
    yearly_data = {variable: {} for variable in variables}
    total_data = {variable: 0 for variable in variables}
    for statement in data:
        date = datetime.strptime(statement["date"][0:10], '%Y-%m-%d')
        if "period" not in statement:
            statement["period"] = "Q" + str(date.month//4 + 1)
        name = str(date.year) + " " + statement["period"]

        for variable in variables:
            already_exist = False
            if date.year not in yearly_data[variable]:
                yearly_data[variable][date.year] = {"children": [], "value": 0, 'name': str(date.year)}
            if unique:
                for child in yearly_data[variable][date.year]["children"]:
                    if child["name"] == name:
                        already_exist = True
            if not already_exist:
                if aggregation_method == 'sum':
                    total_data[variable] += statement[variable]
                    yearly_data[variable][date.year]["value"] += statement[variable]
                elif aggregation_method == "last":
                    total_data[variable] = statement[variable]
                    yearly_data[variable][date.year]["value"] = statement[variable]
                yearly_data[variable][date.year]["children"].append({"name": name, "value": statement[variable], 'children': []})
    for variable in variables:
        yearly_data[variable] = {"name": "Company",
                                 "children": [yearly_data[variable][year] for year in yearly_data[variable]],
                                 "value": total_data[variable]}
    return yearly_data


def plotHistoricalData(data, title, variable_name, display_format):
    p = figure(title=title, sizing_mode='stretch_both', toolbar_location=None)
    p.add_tools(HoverTool(
        tooltips=[("Date", "@Date"), (variable_name, " @" + variable_name + display_format)],
        formatters={'@' + variable_name: 'printf'},
        mode='vline'
    ))
    p.vbar(x="Date", top=variable_name, width=0.9, source=data)
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
    return div, script
