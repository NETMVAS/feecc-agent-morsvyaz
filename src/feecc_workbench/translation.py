
from .config import CONFIG
import csv
import os

current_file = os.path.realpath(__file__)
current_directory = os.path.dirname(current_file)+"/message_lang.csv"

def switch(lang):
    if lang == 'ru':
        return 0
    elif lang == 'en':
        return 1
        
def translation(key: str):

    lang = CONFIG.lang.choose_lang
    
    with open(f'{current_directory}', 'r') as f:
        result={}
        red=csv.DictReader(f)
        for d in red:
            result.setdefault(d['key'],[d['ru'],d['en']])
    
    return result[key][switch(lang)]


