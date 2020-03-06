# -*- coding: utf-8 -*-
"""
Created on Mon Feb 24 21:05:20 2020

@author: Julien
"""
#import all_functions
import pymongo
import time
import pandas as pd
from all_functions import compute_dividends
import os


if __name__ == '__main__':
    start_time = time.time()
    client = pymongo.MongoClient(os.environ['MONGO_URI'].strip("'").replace('test', 'finance'))
    db = client.finance
    collection = db.cleaned_companies
    print("Creating --- %s seconds ---" % (time.time() - start_time))
    request_filter = {
        "Error_stats": False,
        "Stats.Trailing P/E": {"$not": {"$eq": "N/A"}},
        "Stats.Payout Ratio": {"$not": {"$eq": "N/A"}},
        "Stats.Forward Annual Dividend Rate": {"$not": {"$eq": "N/A"}},
        "Country": "France"
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

    
        

    