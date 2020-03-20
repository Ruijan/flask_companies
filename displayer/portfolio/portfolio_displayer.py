import time
from datetime import datetime, timedelta
from math import pi

import ccy
import numpy as np
import pandas as pd
import pycountry
from babel.numbers import format_currency
from bokeh.embed import components
from bokeh.models import ColumnDataSource
from bokeh.models import HoverTool
from bokeh.palettes import RdYlBu
from bokeh.palettes import Spectral6
from bokeh.plotting import figure
from bokeh.transform import cumsum
from flask import render_template
from pandas import Series

from extractor.dividend_extractor import compute_dividends


def render_portfolio(portfolio, tickers, db_companies, cache):
    transactions_html = ""
    dividends = 0
    net_dividends = 0
    div_3_y = 0
    div_5_y = 0
    payout = 0
    growth = 0
    hist = pd.DataFrame()
    summary = dict()
    is_empty = not portfolio["transactions"]
    for txn in portfolio["transactions"]:
        print("Ticker %s" % (txn["ticker"]))
        start_time = time.time()
        company = db_companies.get(txn["ticker"])
        company["stats"] = dict(
            (k.lower().replace(" ", "_"), v) if isinstance(k, str) else (k, v) for k, v in company["stats"].items())
        print("company db --- %s seconds ---" % (time.time() - start_time))
        country = company["country"] if company["country"] != "USA" else "United States"
        company["currency"] = ccy.countryccy(pycountry.countries.get(name=country).alpha_2.lower())
        print("Get currency name --- %s seconds ---" % (time.time() - start_time))
        if "cagr_3" not in company or np.isnan(company["cagr_3"]):
            div_info = Series(compute_dividends(company))
            company = {**company, **div_info}
            db_companies.update_company(company)
            print("company db update--- %s seconds ---" % (time.time() - start_time))
        txn_hist = compute_history(cache, portfolio, txn, company["currency"])
        hist = add_txn_hist(hist, txn_hist)
        print("txn history --- %s seconds ---" % (time.time() - start_time))
        conversion_rate = get_currency_history(company["currency"], portfolio["currency"], cache,
                                               "1d")
        print("currency hist --- %s seconds ---" % (time.time() - start_time))
        c_div = company["stats"]["forward_annual_dividend_rate"] * txn["shares"] * conversion_rate.values[0]
        dividends += c_div
        net_dividends += get_net_dividend(c_div, company["country"])
        div_3_y += c_div * ((1 + company["cagr_3"]) ** 3)
        div_5_y += c_div * ((1 + company["cagr_5"]) ** 5)
        payout += company["payout_ratio"] * txn["total"]
        growth += company["continuous_dividend_growth"] * txn["total"]
        add_transaction_to_summary(c_div, company, summary, txn, txn_hist)
        transactions_html = add_transaction_to_table(portfolio["currency"], transactions_html, txn)
        print("Create variables --- %s seconds ---" % (time.time() - start_time))
    for ticker, position in summary.items():
        position["total_change_perc"] = position["total_change"] / position["total"] * 100
        position["daily_change_perc"] = position["daily_change"] / position["previous_total"] * 100
    portfolio_html = get_portfolio_summary_table(summary, portfolio["currency"])
    dividends_plot, div_script = get_portfolio_dividends_plot(hist)
    sector_pie_plot, sector_pie_script = get_pie_plot(summary, "sector", "total")
    industry_pie_plot, industry_pie_script = get_pie_plot(summary, "industry", "total")
    company_pie_plot, company_pie_script = get_pie_plot(summary, "name", "total")
    sector_pie_div_plot, sector_pie_div_script = get_pie_plot(summary, "sector", "dividends")
    industry_pie_div_plot, industry_pie_div_script = get_pie_plot(summary, "industry", "dividends")
    company_pie_div_plot, company_pie_div_script = get_pie_plot(summary, "name", "dividends")
    close, script = get_portfolio_history_plot(hist)
    diff_price = (hist["Close"].values.flatten() - hist["Amount"].values.flatten()).tolist() if not is_empty else None
    daily_change = get_price_change(diff_price, 2, portfolio["total"]) if not is_empty else 0
    week_change = get_price_change(diff_price, 7, portfolio["total"]) if not is_empty else 0
    month_change = get_price_change(diff_price, 30, portfolio["total"]) if not is_empty else 0
    year_change = get_price_change(diff_price, 365, portfolio["total"]) if not is_empty else 0
    total_change = diff_price[-1] / portfolio["total"] * 100 if not is_empty else 0
    all_tickers = tickers[["Ticker", "Name"]].set_index("Ticker").to_dict()["Name"]
    return render_template("portfolio.html",
                           name=portfolio["name"],
                           total=format_amount(portfolio["total"], portfolio["currency"]),
                           currency=portfolio["currency"],
                           transactions=transactions_html,
                           portfolio=portfolio_html,
                           div_yield="{:.2f}%".format(dividends / portfolio["total"] * 100) if not is_empty else "- %",
                           annual_div=format_amount(dividends, portfolio["currency"]),
                           received_div=format_amount(hist["DividendCumSum"][-1],
                                                      portfolio["currency"]) if not is_empty else "-",
                           net_div_yield="{:.2f}%".format(
                               net_dividends / portfolio["total"] * 100) if not is_empty else "-",
                           net_annual_div=format_amount(net_dividends, portfolio["currency"]),
                           net_received_div=format_amount(hist["DividendCumSum"][-1] * net_dividends / dividends,
                                                          portfolio["currency"]) if not is_empty else "-",
                           cagr3="{:.2f}%".format(
                               ((div_3_y / dividends) ** (1 / 3) - 1) * 100) if not is_empty else "-",
                           cagr5="{:.2f}%".format(
                               ((div_5_y / dividends) ** (1 / 5) - 1) * 100) if not is_empty else "-",
                           payout="{:.2f}%".format(payout / portfolio["total"] * 100) if not is_empty else "-",
                           growth="{:.0f}".format(growth / portfolio["total"]) if not is_empty else "-",
                           tickers=all_tickers,
                           today_change=format_percentage_change(daily_change),
                           week_change=format_percentage_change(week_change),
                           month_change=format_percentage_change(month_change),
                           year_change=format_percentage_change(year_change),
                           total_change=format_percentage_change(total_change),
                           script=script,
                           close=close,
                           div_script=div_script,
                           dividends_plot=dividends_plot,
                           sector_pie_plot=sector_pie_plot,
                           sector_pie_script=sector_pie_script,
                           industry_pie_plot=industry_pie_plot,
                           industry_pie_script=industry_pie_script,
                           company_pie_plot=company_pie_plot,
                           company_pie_script=company_pie_script,
                           sector_pie_div_plot=sector_pie_div_plot,
                           sector_pie_div_script=sector_pie_div_script,
                           industry_pie_div_plot=industry_pie_div_plot,
                           industry_pie_div_script=industry_pie_div_script,
                           company_pie_div_plot=company_pie_div_plot,
                           company_pie_div_script=company_pie_div_script
                           )


def get_pie_plot(summary, field, value):
    sectors = {}
    for ticker, company in summary.items():
        if company[field] not in sectors:
            sectors[company[field]] = 0
        sectors[company[field]] += company[value]
    data = pd.Series(sectors).sort_values().reset_index(name='value').rename(columns={'index': field})
    data['angle'] = data['value'] / data['value'].sum() * 2 * pi
    nb_colors = len(sectors) if len(sectors) >= 3 else 3
    data['color'] = RdYlBu[nb_colors]

    p = figure(sizing_mode='scale_width', toolbar_location=None,
               tools="hover", tooltips="@" + field + ": @value", x_range=(-1, 3.0), aspect_ratio=1920.0 / 1280)

    r = p.annular_wedge(x=0, y=1, inner_radius=0.65, outer_radius=1, direction="anticlock",
                        start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
                        line_color="white", fill_color='color', source=data, legend_field=field)

    p.axis.axis_label = None
    p.axis.visible = False
    p.grid.grid_line_color = None
    prettify_plot(p)
    p.legend.location = "center_right"
    script, dividends = components(p)
    return dividends, script


def add_transaction_to_summary(c_div, company, summary, txn, txn_hist):
    if txn["ticker"] not in summary:
        summary[txn["ticker"]] = {"total": 0, "shares": 0, "dividends": 0, "daily_change": 0,
                                  "daily_change_perc": 0, "total_change": 0, "total_change_perc": 0,
                                  "previous_total": 0,
                                  "name": txn["name"], "sector": company["sector"], "industry": company["industry"],
                                  "country": company["country"], "currency": company["currency"]}
    summary[txn["ticker"]]["shares"] += txn["shares"]
    summary[txn["ticker"]]["dividends"] += c_div
    summary[txn["ticker"]]["total"] += txn["total"]
    previous_amount = (txn_hist["Close"][-2] if txn_hist.shape[0] > 1 else txn["total"])
    summary[txn["ticker"]]["daily_change"] += txn_hist["Close"][-1] - previous_amount
    summary[txn["ticker"]]["previous_total"] += previous_amount
    summary[txn["ticker"]]["total_change"] += txn_hist["Close"][-1] - txn["total"]


def get_portfolio_summary_table(summary, currency):
    portfolio_html = ""
    for ticker, position in summary.items():
        portfolio_html += "<tr>"
        portfolio_html += "<td class='ticker'>" + ticker + "</td>"
        portfolio_html += "<td>" + position["name"] + "</td>"
        portfolio_html += "<td>" + str(position["shares"]) + "</td>"
        portfolio_html += "<td>" + format_price_change(position["daily_change"], currency) + " (" + \
                          format_percentage_change(position["daily_change_perc"]) + ")" + "</td>"
        portfolio_html += "<td>" + format_price_change(position["total_change"], currency) + " (" + \
                          format_percentage_change(position["total_change_perc"]) + ")" + "</td>"
        portfolio_html += "<td>" + format_amount(position["total"], position["currency"]) + "</td>"
        portfolio_html += "</tr>"
    return portfolio_html


def format_amount(amount, currency):
    return format_currency(amount, currency, locale='en_US')


def get_history(cache, ticker, date, shares, end_date=datetime.now()):
    hist = cache.get(ticker)
    mask = (hist.index >= date) & (hist.index <= end_date)
    hist = hist.loc[mask]
    hist = hist.drop(["Open", "High", "Low", "Volume", "Stock Splits"], axis=1)
    hist["Dividends"] *= shares
    hist["Close"] *= shares
    return hist


def get_currency_history(currency, target_currency, cache, period="max"):
    max_days = get_max_days_from_string(period)
    if currency != target_currency:
        ticker = currency + target_currency + '=X'
        if currency == "USD":
            ticker = target_currency + '=X'
        return cache.get(ticker)["Close"]
    base = datetime.today()
    date_list = [base - timedelta(days=x) for x in range(max_days)]
    currency = pd.Series(data=[1] * len(date_list), index=date_list)
    return currency


def get_max_days_from_string(period):
    if period == "max":
        max_days = 50 * 365  # 50 years of days
    elif period == "1d":
        max_days = 1
    elif period == "5d":
        max_days = 5
    elif period == "1mo":
        max_days = 30
    elif period == "3mo":
        max_days = 90
    elif period == "6mo":
        max_days = 180
    elif period == "1y":
        max_days = 365
    elif period == "2y":
        max_days = 2 * 365
    elif period == "5y":
        max_days = 5 * 365
    elif period == "10y":
        max_days = 10 * 365
    return max_days


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


def format_percentage_change(percentage_change):
    formatted_change = "-"
    if percentage_change is not None:
        style = "negative" if percentage_change < 0 else "positive"
        formatted_change = "<span class='" + style + "'>{:.2f}%</span>".format(percentage_change)
    return formatted_change


def format_price_change(price_change, currency):
    formatted_change = "-"
    if price_change is not None:
        style = "negative" if price_change < 0 else "positive"
        formatted_change = "<span class='" + style + "'>" + format_amount(price_change, currency) + "</span>"
    return formatted_change


def get_price_change(close_prices, days, total):
    return (close_prices[-1] - close_prices[-days]) / total * 100 if days < len(close_prices) else None


def get_portfolio_dividends_plot(hist):
    dividends = ""
    script = ""
    if hist.shape[0] > 0:
        hist["DividendCumSum"] = hist["Dividends"].cumsum()
        amount = hist["Dividends"].resample("M").sum()
        dates = amount.index
        data = {'Date': dates.to_pydatetime().tolist(),
                'Amount': amount.values.flatten().tolist()}
        p = figure(sizing_mode='scale_width', toolbar_location=None, x_axis_type='datetime',
                   aspect_ratio=1920.0 / 1080.0)
        p.toolbar.active_drag = None
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Spectral6[0],
                             legend_label="Dividends")
        p.add_tools(HoverTool(
            tooltips=[("Date", "@Date{%F}"), ("Amount", " @Amount{%0.2f}")],
            formatters={'@Date': 'datetime',
                        '@Amount': 'printf'},
            mode='vline',
            renderers=[amount_plot]
        ))
        prettify_plot(p)
        script, dividends = components(p)
    return dividends, script


def get_portfolio_cum_dividends_plot(hist):
    dividends = ""
    script = ""
    if hist.shape[0] > 0:
        hist["DividendCumSum"] = hist["Dividends"].cumsum()
        amount = hist["DividendCumSum"].resample("D").ffill()
        dates = amount.index
        data = {'Date': dates.to_pydatetime().tolist(),
                'Amount': amount.values.flatten().tolist()}
        p = figure(sizing_mode='scale_width', toolbar_location=None, x_axis_type='datetime',
                   aspect_ratio=1920.0 / 1080.0)
        p.toolbar.active_drag = None
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Spectral6[0],
                             legend_label="Dividends")
        p.add_tools(HoverTool(
            tooltips=[("Date", "@Date{%F}"), ("Amount", " @Amount{%0.2f}")],
            formatters={'@Date': 'datetime',
                        '@Amount': 'printf'},
            mode='vline',
            renderers=[amount_plot]
        ))
        prettify_plot(p)
        script, dividends = components(p)
    return dividends, script


def prettify_plot(p):
    p.xgrid.grid_line_color = None
    p.y_range.start = 0
    p.background_fill_alpha = 0.
    p.border_fill_alpha = 0.
    p.outline_line_alpha = 0.
    p.xaxis.axis_line_color = "cornsilk"
    p.xaxis.major_label_text_color = "cornsilk"
    p.yaxis.axis_line_color = "cornsilk"
    p.yaxis.major_label_text_color = "cornsilk"
    p.xaxis.major_tick_line_color = "cornsilk"
    p.xaxis.major_tick_line_width = 3
    p.yaxis.major_tick_line_color = "cornsilk"
    p.yaxis.minor_tick_line_color = None
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"
    p.legend.background_fill_alpha = 0.0
    p.legend.border_line_width = 0.0
    p.legend.label_text_color = "cornsilk"


def get_portfolio_history_plot(hist):
    close = ""
    script = ""
    if hist.shape[0] > 0:
        close_price = hist["Close"].resample("D").ffill()
        amount = hist["Amount"].resample("D").ffill()
        dates = amount.index
        data = {'Date': dates.to_pydatetime().tolist(),
                'Close': close_price.values.flatten().tolist(),
                'Amount': amount.values.flatten().tolist()}
        p = figure(sizing_mode='scale_width', toolbar_location=None, x_axis_type='datetime',
                   aspect_ratio=1920.0 / 1080.0)
        p.toolbar.active_drag = None
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Spectral6[1],
                             legend_label="Invested")
        close_plot = p.line(x="Date", y="Close", line_width=5, source=ColumnDataSource(data=data), color=Spectral6[0],
                            legend_label="Close Price")

        p.add_tools(HoverTool(
            tooltips=[("Date", "@Date{%F}"), ("Close", " @Close{%0.2f}"), ("Invested", " @Amount{%0.2f}")],
            formatters={'@Close': 'printf',
                        '@Date': 'datetime',
                        '@Amount': 'printf'},
            mode='vline',
            renderers=[close_plot]
        ))
        prettify_plot(p)
        script, close = components(p)
    return close, script


def compute_history(cache, portfolio, txn, currency):
    start_time = time.time()
    txn_hist = get_history(cache, txn["ticker"], datetime.strptime(txn["date"], "%Y-%m-%d"), txn["shares"])
    currency_hist = get_currency_history(currency, portfolio["currency"], cache)
    mask = (currency_hist.index >= np.min(txn_hist.index)) & (currency_hist.index <= datetime.now())
    currency_hist = currency_hist.loc[mask]
    txn_hist["Amount"] = [txn["price"] * txn["shares"]] * len(txn_hist["Close"])
    txn_hist["Close"] = txn_hist["Close"].mul(currency_hist, fill_value=1)
    txn_hist["Dividends"] = txn_hist["Dividends"].mul(currency_hist, fill_value=1)
    return txn_hist


def add_txn_hist(hist, txn_hist):
    if hist.empty:
        hist = txn_hist
    else:
        new_hist = txn_hist.join(hist, lsuffix='', rsuffix='_right', how="outer")
        new_hist = new_hist.astype(float)
        new_hist = new_hist.interpolate(method='linear', axis=0).ffill()
        txn_hist = new_hist[["Close_right", "Dividends_right", "Amount_right"]].set_axis(
            ["Close", "Dividends", "Amount"], axis=1, inplace=False)
        hist = new_hist[["Close", "Dividends", "Amount"]].add(txn_hist, fill_value=0)
    return hist


def add_transaction_to_table(currency, transactions_html, txn):
    transactions_html += "<tr>"
    transactions_html += "<td class='ticker'>" + txn["ticker"] + "</td>"
    transactions_html += "<td>" + txn["name"] + "</td>"
    transactions_html += "<td>" + str(txn["shares"]) + "</td>"
    transactions_html += "<td>" + "{:.2f}".format(txn["price_COS"]) + "</td>"
    transactions_html += "<td>" + format_amount(txn["price"], currency) + "</td>"
    transactions_html += "<td>" + format_amount(txn["fees"], currency) + "</td>"
    transactions_html += "<td>" + txn["date"] + "</td>"
    transactions_html += "<td>" + format_amount(txn["total"], currency) + "</td>"
    transactions_html += "<td>" \
                         "<form target='_self' method='post' id='del_txn_" + str(txn["id"]) + "'>" + \
                         "<input value='" + str(txn["id"]) + "' name='id' hidden=True>" + \
                         "<input value='del' name='action' hidden=True>" + \
                         "<div class='del_button' onclick='document.getElementById(\"del_txn_" + str(txn["id"]) + \
                         "\").submit();'>DEL</div>" \
                         "</form>" \
                         "</td>"
    transactions_html += "</tr>"
    return transactions_html
