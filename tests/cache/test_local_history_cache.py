import unittest
from datetime import datetime, timedelta

from src.cache.local_history_cache import get_range, LocalHistoryCache


class HistoryCacheTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(HistoryCacheTestCase, self).__init__(*args, **kwargs)
        self.cache = LocalHistoryCache.get_instance()

    def test_init_twice_should_throw(self):
        with self.assertRaises(Exception) as context:
            LocalHistoryCache()
        self.assertTrue('This class is a singleton!' in str(context.exception))

    def test_get_one_week_data(self):
        pass

    def test_get_one_day_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '1d', None)
        self.assertLessEqual((end_date - today).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d %H:%M:%S") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual((start_date - (today - timedelta(days=1))).days, 0, 'Expect start_date to be 1 day ago')

    def test_get_five_days_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5d', None)
        self.assertLessEqual((end_date - today).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d %H:%M:%S") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual((start_date - (today - timedelta(days=5))).days, 0, 'Expect start_date to be 5 days ago')

    def test_get_five_weeks_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5w', None)
        self.assertLessEqual((end_date - today).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d %H:%M:%S") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual((start_date - (today - timedelta(weeks=5))).days, 0, 'Expect start_date to be 5 weeks ago')

    def test_get_five_months_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5m', None)
        self.assertEqual((end_date - today).days, 0,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d %H:%M:%S") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual((start_date - (today - timedelta(weeks=5*4))).days, 0, 'Expect start_date to be 5 months ago')

    def test_get_five_years_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5y', None)
        self.assertLessEqual((end_date - today).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d %H:%M:%S") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual((start_date - (today - timedelta(weeks=5*52))).days, 0, 'Expect start_date to be 5 years ago')


if __name__ == '__main__':
    unittest.main()
