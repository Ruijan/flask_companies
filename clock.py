from apscheduler.schedulers.blocking import BlockingScheduler
from crawler.companies_crawler import process_companies
import pymongo
import pandas as pd
import os

sched = BlockingScheduler()


@sched.scheduled_job('interval', minutes=3)
def timed_job():
    print('This job is run every three minutes.')
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    db = client.finance
    collection = db.cleaned_companies
    companies = pd.DataFrame.from_records(collection.find())
    companies = companies.sample(frac=1).reset_index(drop=True)
    logs = ""
    process_companies(companies, db, logs, 30)
    client.close()


# @sched.scheduled_job('cron', minutes=1)
# def scheduled_job():
#     print('This job is run every day every 15min.')
#     client = pymongo.MongoClient(os.environ["MONGO_URI"])
#     db = client.finance
#     collection = db.cleaned_companies
#     companies = pd.DataFrame.from_records(collection.find())
#     companies = companies.sample(frac=1).reset_index(drop=True)
#     logs = ""
#     process_companies(companies, db, logs, 30)
#     client.close()


sched.start()
