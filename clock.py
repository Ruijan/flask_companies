from apscheduler.schedulers.blocking import BlockingScheduler
from crawler.companies_crawler import process_companies
import pymongo
import pandas as pd
import os

sched = BlockingScheduler()


@sched.scheduled_job('interval', minutes=5)
def timed_job():
    print('This job is run every five minutes.')
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    db = client.finance
    collection = db.cleaned_companies
    companies = pd.DataFrame.from_records(collection.find().sort("last_update", 1).limit(100))
    tickers = list(companies.ticker.values)
    tickers = pd.DataFrame.from_records(db.tickers.find({"Ticker": {"$in": tickers}}))
    companies = companies.sample(frac=1).reset_index(drop=True)
    logs = ""
    process_companies(companies, tickers, db, logs, 4*60)
    client.close()


sched.start()
