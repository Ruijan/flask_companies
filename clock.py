from apscheduler.schedulers.blocking import BlockingScheduler
from src.crawler.companies_crawler import process_companies
import pymongo
import pandas as pd
import os
from multiprocessing.pool import ThreadPool
import sys

scheduler = BlockingScheduler()


@scheduler.scheduled_job('interval', minutes=5)
def timed_job():
    print('This job is run every five minutes.')
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    db = client.finance
    collection = db.cleaned_companies
    pool = ThreadPool(processes=5)
    try:
        companies = pd.DataFrame.from_records(collection.find().sort("last_update", 1).limit(100))
        tickers = list(companies.ticker.values)
        tickers = pd.DataFrame.from_records(db.tickers.find({"Ticker": {"$in": tickers}}))
        companies = companies.sample(frac=1).reset_index(drop=True)
        logs = ""
        process_companies(companies, pool, tickers, db, logs, 4 * 60)
    except (RuntimeError, TypeError, NameError) as err:
        print("Error: {0}".format(err))
    else:
        print("Unexpected error:", sys.exc_info()[0])
    client.close()
    pool.terminate()


scheduler.start()
