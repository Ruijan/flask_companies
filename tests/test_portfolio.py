import unittest
import pandas as pd
from datetime import datetime

from src.currency import Currency
from src.portfolio.portfolio import Portfolio

number_of_month_in_year = 12


class PortfolioTestCase(unittest.TestCase):
    def setUp(self):
        super().__init__()
        self.name = "My portfolio"
        self.user = "user_id"
        self.stats = pd.DataFrame()
        self.history = pd.DataFrame()
        self.dividend_transactions = []
        self.last_update = datetime.now()
        self.positions = dict()
        self.currency = Currency("USD")
        self.identifier = "id"
        self.total = 0
        self.current = 0
        self.transactions = []

    def test_portfolio_creation(self):
        portfolio = Portfolio(self.name, self.user, self.stats, self.history, self.dividend_transactions,
                              self.last_update, self.positions,
                              self.currency, self.identifier, self.total, self.current,
                              self.transactions)
        self.assertEqual(self.name, portfolio.name)
        self.assertEqual(self.user, portfolio.user)
        self.assertTrue(portfolio.stats.equals(self.stats))
        self.assertTrue(portfolio.history.equals(self.history))
        self.assertEqual(self.last_update, portfolio.last_update)
        self.assertEqual(self.positions, portfolio.positions)
        self.assertEqual(self.currency, portfolio.currency)
        self.assertEqual(self.identifier, portfolio.id)
        self.assertEqual(self.total, portfolio.total)
        self.assertEqual(self.current, portfolio.current)
        self.assertEqual(self.transactions, portfolio.transactions)

    def test_portfolio_creation_without_optional_fields(self):
        portfolio = Portfolio(self.name, self.user, None, None, None, None, {},
                              self.currency, self.identifier, None, None,
                              None)
        self.assertEqual(self.name, portfolio.name)
        self.assertEqual(self.user, portfolio.user)
        self.assertTrue(portfolio.stats.equals(self.stats))
        self.assertTrue(portfolio.history.equals(self.history))
        self.assertLess((self.last_update - portfolio.last_update).total_seconds(), 1)
        self.assertEqual(self.positions, portfolio.positions)
        self.assertEqual(self.currency, portfolio.currency)
        self.assertEqual(self.identifier, portfolio.id)
        self.assertEqual(self.total, portfolio.total)
        self.assertEqual(self.current, portfolio.current)
        self.assertEqual(self.transactions, portfolio.transactions)

    def test_portfolio_creation_without_name(self):
        with self.assertRaises(AttributeError):
            Portfolio("", self.user, self.stats, self.history, self.dividend_transactions, self.last_update, self.positions,
                      self.currency, self.identifier, self.total, self.current,
                      self.transactions)

    def test_portfolio_creation_with_wrong_currency(self):
        with self.assertRaises(AttributeError):
            Portfolio(self.name, self.user, self.stats, self.history,self.dividend_transactions, self.last_update, self.positions,
                      "USD", self.identifier, self.total, self.current,
                      self.transactions)
