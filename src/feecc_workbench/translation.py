from ..config import CONFIG
import csv
import os

current_file = os.path.realpath(__file__)
current_directory = os.path.dirname(current_file) + "/message_lang.csv"


def translation(key: str):
    lang = CONFIG.language_message

    with open(f"{current_directory}", "r") as f:
        result = {}
        red = csv.DictReader(f, delimiter=";")
        for d in red:
            result.setdefault(d["key"], [d[lang]])
    return result[key][0]
