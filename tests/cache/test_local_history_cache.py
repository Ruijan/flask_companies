import unittest
from datetime import datetime, timedelta
from time import strftime

from src.cache.local_history_cache import get_range


class MyTestCase(unittest.TestCase):
    def test_get_one_day_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '1d', None)
        self.assertLessEqual((today - end_date).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertLessEqual((today - timedelta(days=1) - start_date).seconds, 1, 'Expect start_date to be 1 day ago')

    def test_get_five_days_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5d', None)
        self.assertLessEqual((today - end_date).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertLessEqual((today - timedelta(days=5) - start_date).seconds, 1, 'Expect start_date to be 5 days ago')

    def test_get_five_weeks_range(self):
        today = datetime.today()
        (end_date, start_date) = get_range(None, '5w', None)
        self.assertLessEqual((today - end_date).seconds, 1,
                             'Expect end_date to be today. Received: ' + end_date.strftime(
                                 "%Y-%m-%d") + " compared to " + today.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertLessEqual((today - timedelta(weeks=5) - start_date).seconds, 1,
                             'Expect start_date to be 5 weeks ago')


if __name__ == '__main__':
    unittest.main()
