# -*- coding: utf-8 -*-
"""
Created on Mon Feb 24 13:00:36 2020

@author: Julien
"""
from datetime import datetime, date
import pandas as pd
import numpy as np
import math


def print_companies_to_html(df):
    df.columns = df.columns.str.strip().str.replace('_', ' ')
    print(df.columns)
    df.rename(columns=lambda x: x[0].upper() + x[1:], inplace=True)
    keys = ["Name", "Sector", "Country", "Trailing P/E", "CAGR 3", "CAGR 5", "Payout ratio", "Div. Yield",
            "Continous Dividend Growth", "Div score"]
    percentage_keys = ["CAGR 3", "CAGR 5", "Payout ratio", "Div. Yield"]
    style = {key: lambda x: "{:20,.2f}%".format(100 * x) for key in percentage_keys}
    data = df.sort_values(by=['Div score', "Div. Yield"], ascending=False)[keys]
    html = data.head(50).to_html(formatters=style, index_names=False)
    previous_index = html.find("<tr>", 0)
    index = 0
    while previous_index != -1:
        html = html[:previous_index] + "<tr onclick='showCompany(\"" + \
               str(data.index.values[index]) + "\")'>" + html[previous_index + 4:]
        index += 1
        previous_index = html.find("<tr>", previous_index)

    return html


def compute_dividends(row):
    if "Payout Ratio" in row.stats and "Forward Annual Dividend Yield" in row.stats:
        return get_dividend_features(row.dividend_history, row.stock_splits,
                                     row.stats["Payout Ratio"],
                                     row.stats["Forward Annual Dividend Yield"])
    return get_dividend_features(row.dividend_history, row.stock_splits, 0, 0)


def get_corrected_div_values(dividends, stock_splits):
    temp_dividends = dividends.copy()
    for key in stock_splits.keys():
        key_time = datetime.strptime(key, "%b %d, %Y")
        if stock_splits[key] > 0:
            temp_dividends = {k: v / stock_splits[key] if datetime.strptime(k, "%b %d, %Y") < key_time else v for k, v
                              in temp_dividends.items()}
    return temp_dividends


def get_yearly_dividends(dividends, stock_splits):
    temp_dividends = get_corrected_div_values(dividends, stock_splits)
    dividend_dates = {key: datetime.strptime(key, "%b %d, %Y") for key in dividends.keys()}
    n_div = dict()
    for k, v in dividend_dates.items():
        key = date(v.year, v.month, 1)
        if key in n_div:
            n_div[key] += temp_dividends[k]
        else:
            n_div[key] = temp_dividends[k]
    years = [key.year for key in n_div.keys()]
    n_div_2 = dict.fromkeys(years, 0)
    for k, v in n_div.items():
        n_div_2[k.year] += n_div[k]
    return pd.DataFrame.from_dict(
        {'Date': list(n_div_2.keys()),
         'values': list(n_div_2.values())}).set_index("Date")


def get_continuous_dividend_payment(yearly_dividends):
    count_years = 0
    shifted_dates = yearly_dividends.values[0:-1]
    shifted_div = yearly_dividends.index[0:-1]
    divdiff = (shifted_dates - yearly_dividends.values[1:]) / shifted_dates * 100
    datediff = (shifted_div - yearly_dividends.index[1:]) / shifted_div * 100
    divdiff = divdiff.flatten()
    if len(divdiff) > 0:
        divdiff = np.delete(divdiff, 0)
    nb_tot_years = len(divdiff)
    for index in range(nb_tot_years):
        if divdiff[index] < 0 or datediff[index] > 1:
            return count_years
        count_years += 1
    return count_years


def get_cagr(yearly_dividends, years):
    current_year = datetime.now().year
    if current_year - 1 in yearly_dividends.index and current_year - 1 - years in yearly_dividends.index:
        return (np.power(yearly_dividends.loc[current_year - 1] / yearly_dividends.loc[current_year - 1 - years],
                         1 / years) - 1).values[0]
    elif current_year - 2 in yearly_dividends.index and current_year - 2 - years in yearly_dividends.index:
        return (np.power(yearly_dividends.loc[current_year - 2] / yearly_dividends.loc[current_year - 2 - years],
                         1 / years) - 1).values[0]
    return 0


def get_dividend_features(dividends, stock_splits, payout_ratio, current_yield):
    data = {"CAGR_1": 0, "CAGR_3": 0, "CAGR_5": 0, "CAGR_10": 0, "Continous Dividend Growth": 0,
            "Payout_ratio": payout_ratio, "Div. Yield": current_yield, "div_score": 0}
    yearly_dividends = get_yearly_dividends(dividends, stock_splits)
    data["CAGR_1"] = get_cagr(yearly_dividends, 1)
    data["CAGR_3"] = get_cagr(yearly_dividends, 3)
    data["CAGR_5"] = get_cagr(yearly_dividends, 5)
    data["CAGR_10"] = get_cagr(yearly_dividends, 10)
    data["Continous Dividend Growth"] = get_continuous_dividend_payment(yearly_dividends)
    data["div_score"] = rate_dividends(data)
    return data


def rate_dividends(data):
    score = 0
    max_score = 8
    cagr = [data["CAGR_1"], data["CAGR_3"], data["CAGR_5"], data["CAGR_10"]]
    if data["Div. Yield"] > 0.02:
        score += 1
    if data["Div. Yield"] > 0.05:
        score += 1
    if np.std(cagr) < 0.2 * np.mean(cagr) and np.mean(cagr) > 0:
        score += 1
    if data["CAGR_1"] > 0.03 and data["CAGR_3"] > 0.03 and data["CAGR_5"] > 0.03:
        score += 1
    if data["CAGR_1"] < 0 or data["CAGR_3"] < 0 or data["CAGR_5"] < 0:
        score -= 1
    if data["Continuous Dividend Growth"] > 8:
        score += 1
    if data["Continuous Dividend Growth"] > 16:
        score += 1
    if data["Payout_ratio"] < 1:
        score += 1
    if data["Payout_ratio"] < 0.8:
        score += 1
    return score / max_score
