import pymongo
import os

if __name__ == '__main__':
    client = pymongo.MongoClient(os.environ["MONGO_URI"])
    collections = client.finance.list_collection_names()

    for collection in collections:
        print("Collection: " + collection)
        documents = list(client.finance[collection].find())
        client.staging_finance[collection].drop()

        # Special case for portfolio, we need to remove summary before inserting it as MongoDB does not allow
        # dictionaries to have '.' in their keys when inserted. Replacing the document allows it though.
        if collection != "portfolio":
            for index in range(0, len(documents), 100):
                try:
                    if index + 100 < len(documents):
                        client.staging_finance[collection].insert_many(documents[index:index + 100])
                    else:
                        client.staging_finance[collection].insert_many(documents[index:len(documents)])
                except:
                    for second_index in range(index, index + 100):
                        try:
                            client.staging_finance[collection].insert_one(documents[second_index])
                        except:
                            print("Error while adding documents" + documents[second_index]["ticker"])
        else:
            documents_without_summary = []
            for document in documents:
                temp = document.copy()
                if "summary" in document:
                    temp.pop("summary")
                documents_without_summary.append(temp)
            for index in range(0, len(documents_without_summary), 100):
                if index + 100 < len(documents):
                    client.staging_finance[collection].insert_many(documents_without_summary[index:index + 100])
                else:
                    client.staging_finance[collection].insert_many(
                        documents_without_summary[index:len(documents_without_summary)])
            for index in range(0, len(documents_without_summary)):
                client.staging_finance[collection].find_one_and_replace(
                    {"_id": documents_without_summary[index]["_id"]}, documents[index])
