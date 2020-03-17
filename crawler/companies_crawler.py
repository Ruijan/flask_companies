# -*- coding: utf-8 -*-
import json
import os
import time
from datetime import datetime
from crawler.company_extractor import CompanyExtractor
import pymongo
import pandas as pd


def process_companies(db_companies, companies, db, logs):
    crawler = CompanyExtractor()
    count_error = 0
    failed_companies = dict()
    for index, company in companies.iterrows():
        db_company = db_companies.loc[db_companies['ticker'] == company["Ticker"]]
        db_company.index = [column.lower().replace(" ", "_") for column in db_company.index]
        data, status, temp_logs = crawler.load_data(db_company, logs)
        logs = temp_logs
        dict_data = data.to_dict()
        dict_data["last_update"] = datetime.now()
        previous_company = db.cleaned_companies.find_one_and_replace({'_id': db_company["_id"]}, dict_data)
        if status == "ERROR" or previous_company is None:
            count_error += 1
            failed_companies.append(db_company)
        elif status == "OK":
            count_error = 0
        if count_error > 5:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logs += "[" + timestamp + "] Too many errors, let's slow down"
            time.sleep(60 * 5)
            crawler.reset_session()
            count_error = 0
    if len(failed_companies) > 0 and len(failed_companies) != len(companies):
        process_companies(failed_companies)


def lambda_handler(event, context):
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    db = client.finance
    collection = db.cleaned_companies
    companies = pd.DataFrame.from_records(db.tickers.find())
    db_companies = pd.DataFrame.from_records(collection.find()).reset_index(drop=True)
    companies = companies.sample(frac=1).reset_index(drop=True)
    logs = ""
    process_companies(db_companies, companies, db, logs)
    client.close()
    return {
        'statusCode': 200,
        'body': json.dumps(logs)
    }


if __name__ == '__main__':
    lambda_handler(None, None)
