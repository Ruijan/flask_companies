import datetime
import pandas
import requests


class DividendCalendar:
    calendars = []
    url = 'https://api.nasdaq.com/api/calendar/dividends'
    hdrs = {'Accept': 'application/json, text/plain, */*',
            'DNT': "1",
            'Origin': 'https://www.nasdaq.com/',
            'Sec-Fetch-Mode': 'cors',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0)'}
    start_date = None
    period = 0

    def __init__(self, from_date, period):
        self.start_date = from_date
        self.period = period

    def fetch_calendar(self):
        dates = [self.start_date + datetime.timedelta(days=day) for day in range(0, self.period)]
        lambda_calendar = lambda date: self.calendar(date)
        objects = list(map(lambda_calendar, dates))  # concatenate all the calendars in the class attribute
        concat_df = pandas.concat(self.calendars)
        drop_df = concat_df.dropna(how='any')
        drop_df.set_index('symbol', inplace=True)
        string_format = "%m/%d/%Y"
        drop_df['dividend_Ex_Date'] = pandas.to_datetime(drop_df['dividend_Ex_Date'], format=string_format)
        drop_df['dividend_Ex_Date'] = drop_df['dividend_Ex_Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
        drop_df.columns = ['company', 'date', 'paymentDate', 'recordDate', 'dividend', 'annualDividend',
                           'declarationDate']
        return drop_df

    def scraper(self, date):
        params = {'date': date.strftime(format='%Y-%m-%d')}
        page = requests.get(self.url, headers=self.hdrs, params=params)
        dictionary = page.json()
        return dictionary

    def dict_to_df(self, dicti):
        rows = dicti.get('data').get('calendar').get('rows')
        calendar = pandas.DataFrame(rows)
        self.calendars.append(calendar)
        return calendar

    def calendar(self, date):
        dictionary = self.scraper(date)
        self.dict_to_df(dictionary)
        return dictionary
