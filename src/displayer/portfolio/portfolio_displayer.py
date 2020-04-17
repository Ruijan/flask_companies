import json
import math
from datetime import datetime
from math import pi

from bokeh.colors import RGB
from colour import Color
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
from bokeh.models import GeoJSONDataSource

import matplotlib.cm
from bokeh.models import ColorBar, LogColorMapper, LogTicker, LinearColorMapper, BasicTicker


def render_portfolio(portfolio, tickers, tab):

    is_empty = not portfolio.transactions

    all_tickers = tickers[["Ticker", "Name"]].set_index("Ticker").to_dict()["Name"]
    context = {"name": portfolio.name, "is_empty": is_empty, "tickers": all_tickers, "tab": tab}
    context.update(get_all_price_change(portfolio.history, is_empty, portfolio))
    context.update(get_portfolio_info(portfolio))
    context.update(get_growth_plot(portfolio.positions, portfolio.history, is_empty))
    context.update(get_dividends_plots(portfolio.positions, portfolio.history, is_empty))
    context["portfolio"] = get_portfolio_summary_table(portfolio.positions, portfolio.currency)
    context["upcoming_dividends"] = get_upcoming_dividends(portfolio.positions, portfolio.currency)
    context["transactions"] = get_transaction_table(portfolio)
    context.update(get_world_maps(portfolio.positions))
    context.update(get_dividends_info(portfolio.history, portfolio.stats, portfolio.currency, is_empty))
    return render_template("portfolio.html", **context)


def get_transaction_table(portfolio):
    transactions_html = ""
    for txn in portfolio.transactions:
        transactions_html = add_transaction_to_table(portfolio.currency, transactions_html, txn)
    return transactions_html


def get_upcoming_dividends(summary, currency):
    upcoming_dividends = [{"ticker": key,
                           "amount": format_currency(position["dividends"] / position["dividend_frequency"], currency,
                                                     locale='en_US'),
                           "date": (position["ex_dividend_date"] - datetime.today()).days}
                          for key, position in summary.items() if
                          (position["ex_dividend_date"] - datetime.today()).days > 0]
    upcoming_dividends = sorted(upcoming_dividends, key=lambda x: x["date"])
    return upcoming_dividends


def get_world_maps(summary):
    context = {}
    context.update(get_world_map_plot(summary, "total"))
    context.update(get_world_map_plot(summary, "dividends"))
    context.update(get_world_map_plot(summary, "total_change"))
    return context


def get_world_map_plot(summary, value):
    value_per_country = group_value_by_country(summary, value)
    max_value = max(value_per_country.values()) if len(value_per_country.values()) > 0 else 0
    min_value = min(value_per_country.values()) if len(value_per_country.values()) > 0 else 0
    abs_max_value = abs(min_value) if abs(min_value) > abs(max_value) else abs(max_value)
    with open('resources/world_map.json') as f:
        data = json.load(f)
    # No need for Antarctica
    data['features'].pop(6)
    to_be_plotted = data.copy()
    to_be_plotted["features"] = []

    empty_countries = data.copy()
    empty_countries["features"] = []
    if min_value >= 0:
        cmap = matplotlib.cm.get_cmap('inferno')
    else:
        cmap = matplotlib.cm.get_cmap('RdYlGn')
    for i in range(len(data['features'])):
        country = data['features'][i]['id']
        if country in value_per_country:
            data['features'][i]['properties']['amount'] = value_per_country[country]
            if min_value < 0:
                n_value = (value_per_country[country] + abs_max_value) / (2 * abs_max_value)
                data['features'][i]['properties']['color'] = n_value
            else:
                data['features'][i]['properties']['color'] = np.log(value_per_country[country]) / np.log(max_value)
            to_be_plotted["features"].append(data['features'][i])
        else:
            data['features'][i]['properties']['amount'] = 0
            empty_countries["features"].append(data['features'][i])
    geo_source = GeoJSONDataSource(geojson=json.dumps(data))
    p = figure(background_fill_color="lightgrey", sizing_mode='scale_width', toolbar_location=None,
               aspect_ratio=1920.0 / 920)
    temp_geo_source = GeoJSONDataSource(geojson=json.dumps(empty_countries))
    p.patches('xs', 'ys', source=temp_geo_source, color='grey')
    for i in range(len(to_be_plotted['features'])):
        temp_data = to_be_plotted.copy()
        temp_data['features'] = [temp_data['features'][i]]
        temp_geo_source = GeoJSONDataSource(geojson=json.dumps(temp_data))
        ratio = temp_data['features'][0]['properties']['color']
        color = cmap(ratio)
        amount_plot = p.patches('xs', 'ys', source=temp_geo_source,
                                color=RGB(color[0] * 255, color[1] * 255, color[2] * 255))
        p.add_tools(HoverTool(
            tooltips=[("Country", "@name"), ("Invested", "@amount{%0.2f}")],
            formatters={'@amount': 'printf'},
            renderers=[amount_plot]
        ))

    p.multi_line('xs', 'ys', source=geo_source, color='cornsilk', line_width=1.5)
    colors = [matplotlib.colors.rgb2hex(cmap(i / 256.0)) for i in range(256)]
    if min_value >= 0:
        color_mapper = LogColorMapper(palette=colors, low=1, high=max_value)
        ticks = LogTicker()
    else:
        color_mapper = LinearColorMapper(palette=colors, low=-abs_max_value, high=abs_max_value)
        ticks = BasicTicker()
    color_bar = ColorBar(color_mapper=color_mapper, ticker=ticks, border_line_color=None, location=(0, 0),
                         background_fill_alpha=0., label_standoff=12)
    color_bar.major_label_text_color = "white"
    p.add_layout(color_bar, 'right')
    p.background_fill_alpha = 0.
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    p.toolbar.active_drag = None
    p.border_fill_alpha = 0.
    p.outline_line_alpha = 0.
    p.axis.visible = False
    p.xaxis.major_tick_line_color = None  # turn off x-axis major ticks
    p.xaxis.minor_tick_line_color = None  # turn off x-axis minor ticks
    p.yaxis.major_tick_line_color = None  # turn off y-axis major ticks
    p.yaxis.minor_tick_line_color = None  # turn off y-axis minor ticks
    script, world_map = components(p)
    return {"world_map_script_" + value: script, "world_map_plot_" + value: world_map}


def group_value_by_country(summary, value):
    amount_invested = {}
    for _, company in summary.items():
        country = company["country"] if company["country"] != "USA" else "United States"
        country = pycountry.countries.get(name=country).alpha_3
        if country not in amount_invested:
            amount_invested[country] = 0
        amount_invested[country] += company[value]
    return amount_invested


def get_growth_plot(summary, hist, is_empty):
    sector_pie_plot, sector_pie_script = get_pie_plot(summary, "sector", "total")
    industry_pie_plot, industry_pie_script = get_pie_plot(summary, "industry", "total")
    company_pie_plot, company_pie_script = get_pie_plot(summary, "name", "total")
    close, script = get_portfolio_history_plot(hist) if not is_empty else ("", "")
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
    dividends_plot, div_script = get_portfolio_dividends_plot(hist) if not is_empty else ("", "")
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


def get_dividends_info(history, stats, currency, is_empty):
    growth_stability_str = "Highly variable"
    growth_stability = np.std([stats["cagr1"], stats["cagr3"], stats["cagr5"]] * 100) if not is_empty else 0
    if growth_stability < 2.5:
        growth_stability_str = "Very Stable"
    elif growth_stability < 5:
        growth_stability_str = "Stable"
    elif growth_stability < 10:
        growth_stability_str = "Unstable"
    return {"div_yield": "{:.2f}%".format(stats["div_yield"] * 100) if not is_empty else "- %",
            "annual_div": format_amount(stats["div_rate"], currency) if not is_empty else "- %",
            "received_div": format_amount(history["DividendCumSum"][-1], currency) if not is_empty else "-",
            "net_div_yield": "{:.2f}%".format(stats["net_div_yield"] * 100) if not is_empty else "-",
            "net_annual_div": format_amount(stats["net_div_rate"], currency) if not is_empty else "- %",
            "net_received_div": format_amount(history["DividendCumSum"][-1] * stats["net_div_rate"] / stats["div_rate"],
                                              currency) if not is_empty else "-",
            "cagr1": "{:.2f}%".format(stats["cagr1"] * 100) if not is_empty else "-",
            "cagr3": "{:.2f}%".format(stats["cagr3"] * 100) if not is_empty else "-",
            "cagr5": "{:.2f}%".format(stats["cagr5"] * 100) if not is_empty else "-",
            "payout": "{:.2f}%".format(stats["payout_ratio"] * 100) if not is_empty else "-",
            "growth": "{:.0f}".format(stats["years_of_growth"]) if not is_empty else "-",
            "growth_stability": growth_stability_str}


def get_portfolio_info(portfolio):
    return {"total": format_amount(portfolio.total, portfolio.currency),
            "current": format_amount(portfolio.current, portfolio.currency),
            "currency": portfolio.currency}


def get_all_price_change(hist, is_empty, portfolio):
    diff_price = (hist["Close"].values.flatten() - hist["Amount"].values.flatten()).tolist() if not is_empty else None

    daily_change = get_price_change(diff_price, 2, portfolio.total) if not is_empty else 0
    week_change = get_price_change(diff_price, 7, portfolio.total) if not is_empty else 0
    month_change = get_price_change(diff_price, 30, portfolio.total) if not is_empty else 0
    year_change = get_price_change(diff_price, 365, portfolio.total) if not is_empty else 0
    total_change = diff_price[-1] / portfolio.total * 100 if not is_empty else 0
    diff_current_price = diff_price[-1] if not is_empty else 0
    diff_today_current_price = diff_price[-1] if not is_empty else 0
    if not is_empty and len(diff_price) > 1:
        diff_today_current_price = diff_price[-1] - diff_price[-2]
    return {"today_change": format_percentage_change(daily_change),
            "month_change": format_percentage_change(month_change),
            "total_change": format_percentage_change(total_change),
            "week_change": format_percentage_change(week_change),
            "year_change": format_percentage_change(year_change),
            "diff_current_price": format_price_change(diff_current_price, portfolio.currency),
            "diff_today_current_price": format_price_change(diff_today_current_price, portfolio.currency)}


def get_pie_plot(summary, field, value):
    sectors = {}
    for ticker, company in summary.items():
        if company[field] not in sectors:
            sectors[company[field]] = 0
        sectors[company[field]] += company[value]
    data = pd.Series(sectors).sort_values().reset_index(name='value').rename(columns={'index': field})
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


def get_portfolio_summary_table(summary, currency):
    portfolio_html = ""
    for ticker, position in summary.items():
        portfolio_html += "<tr onclick='showCompany(\"" + ticker + "\");'>"
        portfolio_html += "<td class='ticker'>" + ticker + "</td>"
        portfolio_html += "<td>" + position["name"] + "</td>"
        portfolio_html += "<td>" + str(position["shares"]) + "</td>"
        portfolio_html += "<td>" + format_amount(position["current_price"], position["currency"]) + "</td>"
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
        p.line(x="Date", y="Amount", line_width=5, source=ColumnDataSource(data=data), color=Accent6[0],
                             legend_label="Invested")
        close_plot = p.line(x="Date", y="Close", line_width=5, source=ColumnDataSource(data=data), color=Accent6[1],
                            legend_label="Close Price")
        p.line(x="Date", y="SP500", line_width=5, source=ColumnDataSource(data=data), color=Accent6[2],
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
