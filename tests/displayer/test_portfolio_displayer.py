import unittest
import pandas as pd
from datetime import datetime

from src.displayer.portfolio.portfolio_displayer import create_dividend_history

number_of_month_in_year = 12


class PortfolioDisplayerTestCase(unittest.TestCase):

    def test_create_dividend_history_from_empty(self):
        history_dict = {"Date": [], "Dividends": [], "Net_Dividends": []}
        history = pd.DataFrame(history_dict, columns=["Date", "Dividends", "Net_Dividends"])
        new_history = create_dividend_history(history)
        self.assertTrue(isinstance(new_history, list))
        self.assertEqual(number_of_month_in_year, len(new_history))
        self.assertEqual([i for i in range(1, 13)], [v["date"].month for v in new_history])
        self.assertTrue(all(v["tax"] == 0 for v in new_history))
        self.assertTrue(all(v["net_amount"] == 0 for v in new_history))

    def test_create_dividend_history_from_multiple_dividend_in_one_month(self):
        today = datetime.today()
        month = today.month
        history_dict = {"Date": [datetime(today.year, month, 1), datetime(today.year, month, 14)],
                        "Dividends": [18.5, 4.5], "Net_Dividends": [14.5, 3]}
        history = pd.DataFrame(history_dict, columns=["Date", "Dividends", "Net_Dividends"]).set_index("Date")
        new_history = create_dividend_history(history)
        self.assertTrue(isinstance(new_history, list))
        self.assertEqual(6 + 1, len(new_history), "Expect number of month to be 7")
        self.assertEqual([i for i in range(month, month+7)], [v["date"].month for v in new_history])
        self.assertEqual(18.5 - 14.5 + 4.5 - 3, new_history[0]["tax"])
        self.assertEqual(14.5 + 3, new_history[0]["net_amount"])

    def test_create_dividend_history_from_two_years(self):
        today = datetime.today()
        month = today.month
        last_year_date = datetime(today.year - 1, month, 1)
        num_months = (today.year - last_year_date.year) * 12 + (today.month - last_year_date.month)
        history_dict = {"Date": [last_year_date],
                        "Dividends": [4.5], "Net_Dividends": [3]}
        history = pd.DataFrame(history_dict, columns=["Date", "Dividends", "Net_Dividends"]).set_index("Date")
        new_history = create_dividend_history(history)
        self.assertTrue(isinstance(new_history, list))
        self.assertEqual(num_months + 7, len(new_history), "Expect number of month to be:" + str(num_months))
        self.assertEqual(4.5 - 3, new_history[0]["tax"])
        self.assertEqual(3, new_history[0]["net_amount"])
