from bokeh.embed import components
from bokeh.models import HoverTool
from bokeh.plotting import figure
from flask import render_template
from src.extractor.dividend_extractor import get_yearly_dividends, get_dividend_features
from datetime import datetime


def display_company(db_company, ticker):
    dividends = get_yearly_dividends(db_company["dividend_history"], db_company["stock_splits"])
    dividend_features = get_dividend_features(db_company["dividend_history"], db_company["stock_splits"],
                                              db_company["stats"]["payout_ratio"],
                                              db_company["stats"]["forward_annual_dividend_yield"])
    dividends = {'Date': list(dividends.index), 'Dividends': dividends.values.flatten().tolist()}
    dividends["Date"].reverse()
    dividends["Dividends"].reverse()
    p = figure(title="Dividend History", sizing_mode='stretch_both', toolbar_location=None)
    p.add_tools(HoverTool(
        tooltips=[("Date", "@Date"), ("Dividends", " @Dividends{%0.2f}")],
        formatters={'@Dividends': 'printf'},
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
                           sector=db_company["sector"],
                           script=script,
                           dividends=div,
                           div_score="{:20,.0f}".format(dividend_features["div_score"] * 100),
                           div_yield="{:20,.2f}%".format(db_company["div_yield"] * 100),
                           cagr1="{:20,.2f}%".format(dividend_features["cagr_1"] * 100),
                           cagr3="{:20,.2f}%".format(dividend_features["cagr_3"] * 100),
                           cagr5="{:20,.2f}%".format(dividend_features["cagr_5"] * 100),
                           payout="{:20,.2f}%".format(dividend_features["payout_ratio"] * 100),
                           growth=str(dividend_features["continuous_dividend_growth"]),
                           last_update=datetime.strftime(db_company["last_update"], "%Y-%m-%d"))
