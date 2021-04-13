class BadTicker(Exception):
    def __init__(self, ticker):
        self.message = "Bad ticker. No company was found for ticker " + ticker
        super().__init__(self.message)