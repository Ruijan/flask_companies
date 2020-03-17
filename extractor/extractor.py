class Extractor:
    session = None

    def get_data(self, data):
        raise NotImplementedError()

    def should_update(self, db_company):
        raise NotImplementedError()

    def update(self, data, db_company):
        raise NotImplementedError()

    def should_clean(self, db_company):
        raise NotImplementedError()

    def clean(self, db_company):
        raise NotImplementedError()
