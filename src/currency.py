from src.cache.currencies import Currencies


class Currency:
    def __init__(self, short_name=None, long_name=None):
        currencies = Currencies.get_instance()

        if short_name is not None:
            if short_name not in currencies:
                raise AttributeError("Currency " + short_name + "not listed")
            self.short = short_name
            self.long = currencies[short_name]
        if long_name is not None:
            if long_name not in currencies.values():
                raise AttributeError("Currency " + long_name + "not listed")
            for short, long in currencies.items():
                if long == long_name:
                    self.short = short
                    break
            self.long = long_name


