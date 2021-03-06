# -*- coding: utf-8 -*-
"""
Created on Mon Feb 24 21:05:20 2020

@author: Julien
"""
#import all_functions
import sys
import time
from all_functions import compute_dividends
from src.crawler.companies_crawler import process_companies
import pymongo
import pandas as pd
import os
from multiprocessing.pool import ThreadPool

global pool


if __name__ == '__main__':
    action = "crawler"
    if action == "crawler":
        client = pymongo.MongoClient(os.environ["MONGO_URI"])
        db = client.finance
        pool = ThreadPool(processes=5)
        collection = db.cleaned_companies
        companies = pd.DataFrame.from_records(collection.find().sort("last_update", 1).limit(100))
        tickers = list(companies.ticker.values)
        tickers = pd.DataFrame.from_records(db.tickers.find({"Ticker": {"$in": tickers}}))

        logs = ""
        process_companies(companies, pool, tickers, db, logs, 200)
        client.close()
        pool.terminate()
    elif action == "screener":
        start_time = time.time()
        client = pymongo.MongoClient(os.environ['MONGO_URI'].strip("'").replace('test', 'staging_finance'))
        db = client.finance
        collection = db.cleaned_companies
        print("Creating --- %s seconds ---" % (time.time() - start_time))
        request_filter = {
            "Error_stats": False,
            "Stats.Trailing P/E": {"$not": {"$eq": "N/A"}},
            "Stats.Payout Ratio": {"$not": {"$eq": "N/A"}},
            "Stats.Forward Annual Dividend Rate": {"$not": {"$eq": "N/A"}}
                    }
        df = pd.DataFrame.from_records(collection.find(request_filter))
        print("Collecting --- %s seconds ---" % (time.time() - start_time))
        df.columns = [c.replace(' ', '_').lower() for c in df.columns]
        print("Renaming --- %s seconds ---" % (time.time() - start_time))
        print(pd.DataFrame(list(df["stats"])).keys())
        df = pd.concat([df, pd.DataFrame(list(df.apply(compute_dividends, axis=1)))], axis=1, sort=False)
        temp_df = pd.DataFrame(list(df["stats"]))
        print("Preprocessing --- %s seconds ---" % (time.time() - start_time))
        print(df.head())
