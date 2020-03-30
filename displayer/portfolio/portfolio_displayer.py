import json
import math
import time
from datetime import datetime, timedelta
from math import pi

import plotly
from bokeh.colors import RGB
from colour import Color
import ccy
import numpy as np
import pandas as pd
import pycountry
from babel.numbers import format_currency
from bokeh.embed import components
from bokeh.models import ColumnDataSource
from bokeh.models import HoverTool
from bokeh.palettes import Accent6
from bokeh.plotting import figure
from bokeh.transform import cumsum
from flask import render_template
from pandas import Series
from bokeh.models import GeoJSONDataSource
from extractor.dividend_extractor import compute_dividends
import matplotlib


def render_portfolio(portfolio, tickers, db_companies, cache, tab, db_portfolio):
    start_time = time.time()
    transactions_html = ""
    dividends = 0
    net_dividends = 0
    div_1_y = 0
    div_3_y = 0
    div_5_y = 0
    payout = 0
    growth = 0
    hist = pd.DataFrame()
    summary = dict()
    is_empty = not portfolio["transactions"]
    ref_hist = pd.DataFrame()
    for txn in portfolio["transactions"]:
        transaction_time = time.time()
        print("---- Ticker %s" % (txn["ticker"]))
        ref_txn = txn.copy()
        ref_txn["ticker"] = "^GSPC"
        ref_txn["shares"] = 1
        company = db_companies.get(txn["ticker"])
        print("---- Get company --- %s seconds ---" % (time.time() - transaction_time))
        company["stats"] = dict(
            (k.lower().replace(" ", "_"), v) if isinstance(k, str) else (k, v) for k, v in company["stats"].items())
        country = company["country"] if company["country"] != "USA" else "United States"
        company["currency"] = ccy.countryccy(pycountry.countries.get(name=country).alpha_2.lower())
        if "cagr_3" not in company or np.isnan(company["cagr_3"]):
            div_info = Series(compute_dividends(company))
            company = {**company, **div_info}
            db_companies.update_company(company)
            print("---- Update company --- %s seconds ---" % (time.time() - transaction_time))
        txn_hist = compute_history(cache, portfolio["currency"], txn, company["currency"])
        print("---- Get company history --- %s seconds ---" % (time.time() - transaction_time))
        ref_txn_hist = compute_history(cache, portfolio["currency"], ref_txn, "USD")
        print("---- Get S&P500 --- %s seconds ---" % (time.time() - transaction_time))
        if len(ref_txn_hist["Close"]) > 0:
            ref_txn["shares"] = ref_txn["total"] / ref_txn_hist["Close"].values[0]
        else:
            ref_txn["shares"] = 0
        ref_txn_hist["Close"] *= ref_txn["shares"]
        ref_txn_hist["Amount"] = ref_txn["total"]
        ref_txn_hist["Net_Dividends"] = ref_txn_hist["Dividends"].apply(get_net_dividend, args=("USA",))
        txn_hist["Net_Dividends"] = txn_hist["Dividends"].apply(get_net_dividend, args=(company["country"],))
        hist = add_txn_hist(hist, txn_hist)
        ref_hist = add_txn_hist(ref_hist, ref_txn_hist)
        print("---- Add txn history --- %s seconds ---" % (time.time() - transaction_time))
        conversion_rate = get_current_conversion_rate(company["currency"], portfolio["currency"], cache)
        print("---- Get currency rate --- %s seconds ---" % (time.time() - transaction_time))
        c_div = company["stats"]["forward_annual_dividend_rate"] * txn["shares"] * conversion_rate
        dividends += c_div
        net_dividends += get_net_dividend(c_div, company["country"])
        div_1_y += c_div * ((1 + company["cagr_1"]) ** 1)
        div_3_y += c_div * ((1 + company["cagr_3"]) ** 3)
        div_5_y += c_div * ((1 + company["cagr_5"]) ** 5)
        payout += company["payout_ratio"] * txn["total"]
        growth += company["continuous_dividend_growth"] * txn["total"]
        add_transaction_to_summary(c_div, company, summary, txn, txn_hist)
        transactions_html = add_transaction_to_table(portfolio["currency"], transactions_html, txn)
    for ticker, position in summary.items():
        position["total_change_perc"] = position["total_change"] / position["total"] * 100
        position["daily_change_perc"] = position["daily_change"] / position["previous_total"] * 100
    update_portfolio(db_portfolio, hist, is_empty, portfolio)
    if not is_empty:
        hist["S&P500"] = ref_hist["Close"]
    print("Collecting data --- %s seconds ---" % (time.time() - start_time))
    all_tickers = tickers[["Ticker", "Name"]].set_index("Ticker").to_dict()["Name"]
    context = get_context(all_tickers, div_1_y, div_3_y, div_5_y, dividends, growth, hist, is_empty, net_dividends,
                          payout,
                          portfolio, summary, tab, transactions_html)
    print("Generate figures and plots --- %s seconds ---" % (time.time() - start_time))

    return render_template("portfolio.html", **context)


def get_context(all_tickers, div_1_y, div_3_y, div_5_y, dividends, growth, hist, is_empty, net_dividends, payout,
                portfolio,
                summary, tab, transactions_html):
    start_time = time.time()

    context = {"name": portfolio["name"], "is_empty": is_empty, "tickers": all_tickers, "tab": tab}
    context.update(get_all_price_change(hist, is_empty, portfolio))
    print("---- Get price change --- %s seconds ---" % (time.time() - start_time))
    context.update(get_portfolio_info(portfolio, hist, is_empty))
    print("---- Get Portfolio info --- %s seconds ---" % (time.time() - start_time))
    context.update(get_growth_plot(summary, hist, is_empty))
    print("---- Get Growth plots --- %s seconds ---" % (time.time() - start_time))
    context.update(get_dividends_plots(summary, hist, is_empty))
    print("---- Get dividends plots --- %s seconds ---" % (time.time() - start_time))
    context["portfolio"] = get_portfolio_summary_table(summary, portfolio["currency"])
    print("---- Get summary table --- %s seconds ---" % (time.time() - start_time))
    context["upcoming_dividends"] = get_upcoming_dividends(summary, portfolio["currency"])
    print("---- Get upcoming dividends table --- %s seconds ---" % (time.time() - start_time))
    context["transactions"] = transactions_html
    context.update(get_world_map_plot(summary))
    context.update(
        get_dividends_info(portfolio, hist, dividends, net_dividends, div_1_y, div_3_y, div_5_y, payout,
                           growth, is_empty))
    print("---- Get dividends info --- %s seconds ---" % (time.time() - start_time))
    return context


def get_upcoming_dividends(summary, currency):
    upcoming_dividends = [{"ticker": key,
                           "amount": format_currency(position["dividends"] / position["dividend_frequency"], currency,
                                                     locale='en_US'),
                           "date": (position["ex_dividend_date"] - datetime.today()).days}
                          for key, position in summary.items() if
                          (position["ex_dividend_date"] - datetime.today()).days > 0]
    upcoming_dividends = sorted(upcoming_dividends, key=lambda x: x["date"])
    return upcoming_dividends


def update_portfolio(db_portfolio, hist, is_empty, portfolio):
    portfolio_changed = False
    new_total = hist["Amount"].values[-1] if not is_empty else 0
    diff_price = (hist["Close"].values.flatten() - hist["Amount"].values.flatten()).tolist() if not is_empty else None
    new_current = new_total + diff_price[-1] if not is_empty else 0
    if new_total != portfolio["total"]:
        portfolio["total"] = new_total
        portfolio_changed = True
    if "current" not in portfolio or new_current != portfolio["current"]:
        portfolio["current"] = new_current
        portfolio_changed = True
    if portfolio_changed:
        db_portfolio.find_one_and_replace({"email": portfolio["email"], "name": portfolio["name"]}, portfolio)


def get_world_map_plot(summary):
    # with open('resources/worldmap3.json') as f:
    #     geojson = json.load(f)
    #     f.close()

    # data = {"Country": list(countries.keys()), "Amount": list(countries.values())}
    # df = pd.DataFrame.from_dict(data)
    # fig = px.choropleth_mapbox(df, geojson=geojson, color="Amount",
    #                            locations="Country", featureidkey="id",
    #                            center={"lat": 45.5517, "lon": -73.7073},
    #                            mapbox_style="carto-positron", zoom=1)
    # fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    # graph_json = json.dumps([fig], cls=plotly.utils.PlotlyJSONEncoder)

    amount_invested = {}
    for ticker, company in summary.items():
        country = company["country"] if company["country"] != "USA" else "United States"
        country = pycountry.countries.get(name=country).alpha_3
        if country not in amount_invested:
            amount_invested[country] = 0
        amount_invested[country] += company["total"]

    max_invested = max(amount_invested.values())

    with open('resources/world_map.json') as f:
        data = json.load(f)
    # No need for Antarctica
    data['features'].pop(6)
    to_be_plotted = data.copy()
    to_be_plotted["features"] = []

    empty_countries = data.copy()
    empty_countries["features"] = []
    cmap = matplotlib.cm.get_cmap('YlOrRd')
    for i in range(len(data['features'])):
        country = data['features'][i]['id']
        if country in amount_invested:
            data['features'][i]['properties']['amount'] = amount_invested[country]
            data['features'][i]['properties']['color'] = amount_invested[country] / max_invested
            to_be_plotted["features"].append(data['features'][i])
        else:
            data['features'][i]['properties']['amount'] = 0
            empty_countries["features"].append(data['features'][i])


    geo_source = GeoJSONDataSource(geojson=json.dumps(data))
    TOOLTIPS = [
        ("Country", "@name"),
        ("Invested", "@amount")
    ]

    p = figure(background_fill_color="lightgrey", sizing_mode='scale_width', toolbar_location=None,
               tools="hover", aspect_ratio=1920.0 / 1080, tooltips=TOOLTIPS)
    temp_geo_source = GeoJSONDataSource(geojson=json.dumps(empty_countries))
    p.patches('xs', 'ys', source=temp_geo_source, color='grey')
    for i in range(len(to_be_plotted['features'])):
        temp_data = to_be_plotted.copy()
        temp_data['features'] = [temp_data['features'][i]]
        temp_geo_source = GeoJSONDataSource(geojson=json.dumps(temp_data))
        ratio = temp_data['features'][0]['properties']['color']
        color = cmap(ratio)
        p.patches('xs', 'ys', source=temp_geo_source, color=RGB(color[0] * 255, color[1] * 255, color[2] * 255))

    p.multi_line('xs', 'ys', source=geo_source, color='white', line_width=1)
    p.background_fill_alpha = 0.
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None

    p.border_fill_alpha = 0.
    p.outline_line_alpha = 0.
    p.axis.visible = False
    p.xaxis.major_tick_line_color = None  # turn off x-axis major ticks
    p.xaxis.minor_tick_line_color = None  # turn off x-axis minor ticks
    p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
    p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
    script, world_map = components(p)
    return {"world_map_script": script, "world_map_plot": world_map}


def get_growth_plot(summary, hist, is_empty):
    sector_pie_plot, sector_pie_script = get_pie_plot(summary, "sector", "total")
    industry_pie_plot, industry_pie_script = get_pie_plot(summary, "industry", "total")
    company_pie_plot, company_pie_script = get_pie_plot(summary, "name", "total")
    close, script = get_portfolio_history_plot(hist)
    return {"script": script if not is_empty else "",
            "close": close if not is_empty else "",
            "sector_pie_plot": sector_pie_plot if not is_empty else "",
            "sector_pie_script": sector_pie_script if not is_empty else "",
            "industry_pie_plot": industry_pie_plot if not is_empty else "",
            "industry_pie_script": industry_pie_script if not is_empty else "",
            "company_pie_plot": company_pie_plot if not is_empty else "",
            "company_pie_script": company_pie_script if not is_empty else ""
            }


def get_dividends_plots(summary, hist, is_empty):
    dividends_plot, div_script = get_portfolio_dividends_plot(hist)
    sector_pie_div_plot, sector_pie_div_script = get_pie_plot(summary, "sector", "dividends")
    industry_pie_div_plot, industry_pie_div_script = get_pie_plot(summary, "industry", "dividends")
    company_pie_div_plot, company_pie_div_script = get_pie_plot(summary, "name", "dividends")
    return {"div_script": div_script if not is_empty else "",
            "dividends_plot": dividends_plot if not is_empty else "",
            "sector_pie_div_plot": sector_pie_div_plot if not is_empty else "",
            "sector_pie_div_script": sector_pie_div_script if not is_empty else "",
            "industry_pie_div_plot": industry_pie_div_plot if not is_empty else "",
            "industry_pie_div_script": industry_pie_div_script if not is_empty else "",
            "company_pie_div_plot": company_pie_div_plot if not is_empty else "",
            "company_pie_div_script": company_pie_div_script if not is_empty else ""}


def get_dividends_info(portfolio, hist, dividends, net_dividends, div_1_y, div_3_y, div_5_y, payout, growth, is_empty):
    growth_stability_str = "Highly variable"
    growth_stability = np.std([div_1_y, div_3_y, div_5_y] * 100)
    if growth_stability < 2.5:
        growth_stability_str = "Very Stable"
    elif growth_stability < 5:
        growth_stability_str = "Stable"
    elif growth_stability < 10:
        growth_stability_str = "Unstable"
    return {"div_yield": "{:.2f}%".format(dividends / portfolio["total"] * 100) if not is_empty else "- %",
            "annual_div": format_amount(dividends, portfolio["currency"]),
            "received_div": format_amount(hist["DividendCumSum"][-1], portfolio["currency"]) if not is_empty else "-",
            "net_div_yield": "{:.2f}%".format(net_dividends / portfolio["total"] * 100) if not is_empty else "-",
            "net_annual_div": format_amount(net_dividends, portfolio["currency"]),
            "net_received_div": format_amount(hist["DividendCumSum"][-1] * net_dividends / dividends,
                                              portfolio["currency"]) if not is_empty else "-",
            "cagr1": "{:.2f}%".format(((div_1_y / dividends) ** (1 / 3) - 1) * 100) if not is_empty else "-",
            "cagr3": "{:.2f}%".format(((div_3_y / dividends) ** (1 / 3) - 1) * 100) if not is_empty else "-",
            "cagr5": "{:.2f}%".format(((div_5_y / dividends) ** (1 / 5) - 1) * 100) if not is_empty else "-",
            "payout": "{:.2f}%".format(payout / portfolio["total"] * 100) if not is_empty else "-",
            "growth": "{:.0f}".format(growth / portfolio["total"]) if not is_empty else "-",
            "growth_stability": growth_stability_str}


def get_portfolio_info(portfolio, hist, is_empty):
    return {"total": format_amount(portfolio["total"], portfolio["currency"]),
            "current": format_amount(portfolio["current"], portfolio["currency"]),
            "currency": portfolio["currency"]}


def get_all_price_change(hist, is_empty, portfolio):
    diff_price = (hist["Close"].values.flatten() - hist["Amount"].values.flatten()).tolist() if not is_empty else None

    daily_change = get_price_change(diff_price, 2, portfolio["total"]) if not is_empty else 0
    week_change = get_price_change(diff_price, 7, portfolio["total"]) if not is_empty else 0
    month_change = get_price_change(diff_price, 30, portfolio["total"]) if not is_empty else 0
    year_change = get_price_change(diff_price, 365, portfolio["total"]) if not is_empty else 0
    total_change = diff_price[-1] / portfolio["total"] * 100 if not is_empty else 0
    diff_current_price = diff_price[-1] if not is_empty else 0
    return {"today_change": format_percentage_change(daily_change),
            "month_change": format_percentage_change(month_change),
            "total_change": format_percentage_change(total_change),
            "week_change": format_percentage_change(week_change),
            "year_change": format_percentage_change(year_change),
            "diff_current_price": format_price_change(diff_current_price, portfolio["currency"])}


def get_pie_plot(summary, field, value):
    start_time = time.time()
    sectors = {}
    for ticker, company in summary.items():
        if company[field] not in sectors:
            sectors[company[field]] = 0
        sectors[company[field]] += company[value]
    print("---- ---- Get price change --- %s seconds ---" % (time.time() - start_time))
    data = pd.Series(sectors).sort_values().reset_index(name='value').rename(columns={'index': field})
    print("---- ---- Create series --- %s seconds ---" % (time.time() - start_time))
    data['angle'] = data['value'] / data['value'].sum() * 2 * pi
    colors = [Color("white")]
    if len(sectors) > 1:
        red = Color("#d94f00")
        white = Color("white")
        blue = Color("#3483d1")
        nb_colors_blue = math.floor(len(sectors) / 2)
        nb_colors_red = math.floor(len(sectors) / 2) + 1
        if len(sectors) % 2:
            nb_colors_blue += 1

        blue_gradient = list(blue.range_to(white, nb_colors_blue))
        red_gradient = list(white.range_to(red, nb_colors_red))
        colors = blue_gradient + red_gradient[1:]
    colors = [color.hex for color in colors]
    data['color'] = colors
    print("---- ---- Generate colors --- %s seconds ---" % (time.time() - start_time))
    p = figure(sizing_mode='scale_width', toolbar_location=None,
               tools="hover", tooltips="@" + field + ": @value", x_range=(-1, 3.0), aspect_ratio=1920.0 / 1280)

    r = p.annular_wedge(x=0, y=1, inner_radius=0.65, outer_radius=1, direction="anticlock",
                        start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
                        line_color="white", fill_color='color', source=data, legend_field=field)
    print("---- ---- Create figure --- %s seconds ---" % (time.time() - start_time))
    p.axis.axis_label = None
    p.axis.visible = False
    p.grid.grid_line_color = None
    prettify_plot(p)
    p.legend.location = "center_right"
    print("---- ---- Prettify --- %s seconds ---" % (time.time() - start_time))
    script, dividends = components(p)
    print("---- ---- Create components --- %s seconds ---" % (time.time() - start_time))
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
    if (datetime.today() - txn_hist.index[-1]).days >= 1:
        summary[txn["ticker"]]["daily_change"] += 0
    else:
        summary[txn["ticker"]]["daily_change"] += txn_hist["Close"][-1] - previous_amount
    summary[txn["ticker"]]["previous_total"] += previous_amount
    summary[txn["ticker"]]["total_change"] += txn_hist["Close"][-1] - txn["total"]
    summary[txn["ticker"]]["ex_dividend_date"] = company["stats"]["ex-dividend_date"]
    div_freq = dict()
    for key, value in company["dividend_history"].items():
        year = datetime.strptime(key, "%b %d, %Y").year
        if year not in div_freq:
            div_freq[year] = 0
        div_freq[year] += 1
    div_freq = [(year, value) for year, value in div_freq.items()]
    div_freq = sorted(div_freq, key=lambda x: x[0], reverse=True)
    div_freq = [x[1] for x in div_freq]
    summary[txn["ticker"]]["dividend_frequency"] = round(np.mean(div_freq[1:5]))


def get_portfolio_summary_table(summary, currency):
    portfolio_html = ""
    for ticker, position in summary.items():
        portfolio_html += "<tr onclick='showCompany(\"" + ticker + "\");'>"
        portfolio_html += "<td class='ticker'>" + ticker + "</td>"
        portfolio_html += "<td>" + position["name"] + "</td>"
        portfolio_html += "<td>" + str(position["shares"]) + "</td>"
        portfolio_html += "<td>" + format_amount(position["dividends"] / position["shares"], currency) + \
                          " ({:.2f}%".format(position["dividends"] / position["total"] * 100) + ")</td>"
        portfolio_html += "<td>" + format_price_change(position["daily_change"], currency) + " (" + \
                          format_percentage_change(position["daily_change_perc"]) + ")" + "</td>"
        portfolio_html += "<td>" + format_price_change(position["total_change"], currency) + " (" + \
                          format_percentage_change(position["total_change_perc"]) + ")" + "</td>"
        portfolio_html += "<td>" + format_amount(position["total"], currency) + "</td>"
        portfolio_html += "</tr>"
    return portfolio_html


def format_amount(amount, currency):
    return format_currency(amount, currency, locale='en_US')


def get_history(cache, ticker, date, shares, end_date=datetime.now()):
    hist = cache.get(ticker, date, end_date)
    hist = hist.drop(["Open", "High", "Low", "Volume", "Stock Splits"], axis=1)
    hist["Dividends"] *= shares
    hist["Close"] *= shares
    return hist


def get_currency_ticker(currency, target_currency):
    ticker = currency
    if currency != target_currency:
        ticker = currency + target_currency + '=X'
        if currency == "USD":
            ticker = target_currency + '=X'
    return ticker


def get_current_conversion_rate(currency, target_currency, cache):
    ticker = get_currency_ticker(currency, target_currency)
    if ticker != currency:
        return cache.get_last_day(ticker)["Close"]
    return 1


def get_currency_history(currency, target_currency, cache, start_date, end_date):
    ticker = get_currency_ticker(currency, target_currency)
    if ticker != currency:
        return cache.get(ticker, start_date, end_date)["Close"]
    base = datetime.today()
    date_list = [base - timedelta(days=x) for x in range((end_date - start_date).days)]
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
        net_amount = hist["Net_Dividends"].resample("M").sum()

        dates = amount.index
        data = {'Date': dates.to_pydatetime().tolist(),
                'Amount': amount.values.flatten().tolist(),
                'Net_Amount': net_amount.values.flatten().tolist()}
        p = figure(sizing_mode='scale_width', toolbar_location=None, x_axis_type='datetime',
                   aspect_ratio=1920.0 / 1080.0)
        p.toolbar.active_drag = None
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Accent6[0],
                             legend_label="Dividends")
        net_amount_plot = p.line(x="Date", y="Net_Amount", line_width=5, source=ColumnDataSource(data=data),
                                 color=Accent6[1],
                                 legend_label="Net Dividends")
        p.add_tools(HoverTool(
            tooltips=[("Date", "@Date{%F}"), ("Amount", " @Amount{%0.2f}"), ("Net Amount", " @Net_Amount{%0.2f}")],
            formatters={'@Date': 'datetime',
                        '@Amount': 'printf',
                        '@Net_Amount': 'printf'},
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
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Accent6[0],
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
        sp500 = hist["S&P500"].resample("D").ffill()
        amount = hist["Amount"].resample("D").ffill()
        dates = amount.index
        data = {'Date': dates.to_pydatetime().tolist(),
                'Close': close_price.values.flatten().tolist(),
                'Amount': amount.values.flatten().tolist(),
                'SP500': sp500.values.flatten().tolist()}
        p = figure(sizing_mode='scale_width', toolbar_location=None, x_axis_type='datetime',
                   aspect_ratio=1920.0 / 1080.0)
        p.toolbar.active_drag = None
        amount_plot = p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Accent6[0],
                             legend_label="Invested")
        close_plot = p.line(x="Date", y="Close", line_width=5, source=ColumnDataSource(data=data), color=Accent6[1],
                            legend_label="Close Price")
        sp500_plot = p.line(x="Date", y="SP500", line_width=5, source=ColumnDataSource(data=data), color=Accent6[2],
                            legend_label="SP500")

        p.add_tools(HoverTool(
            tooltips=[("Date", "@Date{%F}"), ("Close", " @Close{%0.2f}"), ("S&P 500", " @SP500{%0.2f}"),
                      ("Invested", " @Amount{%0.2f}")],
            formatters={'@Close': 'printf',
                        '@SP500': 'printf',
                        '@Date': 'datetime',
                        '@Amount': 'printf'},
            mode='vline',
            renderers=[close_plot]
        ))
        prettify_plot(p)
        script, close = components(p)
    return close, script


def compute_history(cache, portfolio_currency, txn, currency):
    start_time = time.time()
    start_date = datetime.strptime(txn["date"], "%Y-%m-%d")
    txn_hist = get_history(cache, txn["ticker"], start_date, txn["shares"])
    print("---- ---- Get company history --- %s seconds ---" % (time.time() - start_time))
    currency_hist = get_currency_history(currency, portfolio_currency, cache, start_date, datetime.now())
    print("---- ---- Get currency history --- %s seconds ---" % (time.time() - start_time))
    mask = (currency_hist.index >= np.min(txn_hist.index)) & (currency_hist.index <= datetime.now())
    currency_hist = currency_hist.loc[mask]
    print("---- ---- Apply mask --- %s seconds ---" % (time.time() - start_time))
    txn_hist["Amount"] = [txn["price"] * txn["shares"]] * len(txn_hist["Close"])
    txn_hist["Close"] = txn_hist["Close"].mul(currency_hist, fill_value=1)
    txn_hist["Dividends"] = txn_hist["Dividends"].mul(currency_hist, fill_value=1)
    print("---- ---- Set history to currency --- %s seconds ---" % (time.time() - start_time))
    return txn_hist


def add_txn_hist(hist, txn_hist):
    if hist.empty:
        hist = txn_hist
    else:
        new_hist = txn_hist.join(hist, lsuffix='', rsuffix='_right', how="outer")
        new_hist = new_hist.astype(float)
        new_hist["Dividends"].fillna(value=0, inplace=True)
        new_hist["Net_Dividends"].fillna(value=0, inplace=True)
        new_hist = new_hist.interpolate(method='linear', axis=0).ffill()
        txn_hist = new_hist[["Close_right", "Dividends_right", "Amount_right", "Net_Dividends_right", ]].set_axis(
            ["Close", "Dividends", "Amount", "Net_Dividends"], axis=1, inplace=False)
        hist = new_hist[["Close", "Dividends", "Amount", "Net_Dividends"]].add(txn_hist, fill_value=0)
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
