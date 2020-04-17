import re
from datetime import datetime


def str_amount_to_number(str_amount):
    multiplier = 1
    if str_amount[-1] == "M":
        multiplier = 1000000
    elif str_amount[-1] == "B":
        multiplier = 1000000000
    elif str_amount[-1] == "%":
        multiplier = 0.01
    try:
        return float(re.sub("[^0123456789\.]", "", str_amount)) * multiplier
    except:
        return 'N/A'


def is_american_company(country):
    return country == "USA" or country == "United States"


def is_date(string):
    try:
        string = datetime.strptime(string, '%b %d, %Y')
        return True
    except ValueError:
        return False


def check_key_exists(key, company):
    return key in company and company[key] != 'N/A'


def select_value(key, dict1, dict2):
    if dict2[key] != 'N/A' or key not in dict1:
        return dict2[key]
    return dict1[key]


def update_array(old_data, temp_data):
    for array_key in temp_data.keys():
        old_data[array_key] = select_value(array_key, old_data, temp_data)
    return old_data


def clean_key(key):
    if key[-1].isdigit():
        key = key[0:-1]
    if '(' in key:
        string = re.search(r'\(.+\)', key).group(0)
        if is_date(string[1:-1]):
            key = key.replace(string, '')
    if 'shares short (prior month' in key.lower():
        key = 'Shares Short (prior month)'
    key = key.strip(' ').lower().replace(" ", "_")
    return key
