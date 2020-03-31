from datetime import datetime

class CompaniesCache(dict):
    __instance = None
    __collection = None

    @staticmethod
    def get_instance():
        if CompaniesCache.__instance is None:
            CompaniesCache()
        return CompaniesCache.__instance

    def __init__(self, collection):
        if CompaniesCache.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            CompaniesCache.__instance = self
            CompaniesCache.__collection = collection

    def update_company(self, company):
        if company["ticker"] in self:
            company["last_checked"] = datetime.now()
            self[company["ticker"]] = company
            self.__collection.find_one_and_replace({"ticker": company["ticker"]}, company)

    def get(self, key):
        if key not in self:
            company = self.__collection.find_one({"ticker": key})
            company["last_checked"] = datetime.now()
            self[key] = company
        elif (datetime.now() - self[key]["last_update"]).days > 1 and (datetime.now() - self[key]["last_checked"]).seconds >= 300:
            company = self.__collection.find_one({"ticker": key})
            company["last_checked"] = datetime.now()
            self[key] = company
        return self[key]
