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
            self[company["ticker"]] = company
            self.__collection.find_one_and_replace({"ticker": company["ticker"]}, company)

    def get(self, key):
        if key not in self:
            company = self.__collection.find_one({"ticker": key})
            self[key] = company
        return self[key]
