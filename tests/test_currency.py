import unittest

from src.currency import Currency

number_of_month_in_year = 12


class CurrencyTestCase(unittest.TestCase):
    def test_currency_creation_with_short_name(self):
        short_name = "USD"
        currency = Currency(short_name)
        self.assertEqual(short_name, currency.short)

    def test_currency_creation_with_long_name(self):
        long_name = "Euro"
        short_name = "EUR"
        currency = Currency(long_name=long_name)
        self.assertEqual(long_name, currency.long)
        self.assertEqual(short_name, currency.short)

    def test_currency_creation_with_wrong_currency_should_throw(self):
        short_name = "BAP"
        with self.assertRaises(AttributeError):
            Currency(short_name)
