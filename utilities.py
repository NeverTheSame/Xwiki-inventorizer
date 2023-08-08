import os
from datetime import datetime
import json


def transform_datetime(datetime_str):
    if '_' in datetime_str:
        dt = datetime.strptime(datetime_str, "%Y_%m_%d")
        transformed_datetime = dt.strftime("%b, %d, %Y")
    else:
        dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")
        transformed_datetime = dt.strftime("%b, %d, %Y. %H:%M")
    return transformed_datetime



def split_leaf(page_url, splitter):
    if splitter in page_url:
        base_url, article_url_leaf = page_url.split(splitter, 1)
    return article_url_leaf


def return_clear_page_url(article_url_leaf, page_url):
    clear_page_url = page_url
    # problematic_units.json: article-with-%5B
    if "%5B" in article_url_leaf:
        print(f"Skipping {page_url} due to the restricted symbols in URL")
        clear_page_url = page_url.replace("xwiki", "xwiki-sup")

    # problematic_units.json: article-with-%3A
    if "%3A" in article_url_leaf:
        print(f"Skipping {page_url} due to the restricted symbols in URL")
        clear_page_url = page_url.replace("xwiki", "xwiki-sup")

    # problematic_units.json: article-with-%60
    if "%60" in article_url_leaf:
        print(f"Skipping {page_url} due to the restricted symbols in URL")
        clear_page_url = page_url.replace("xwiki", "xwiki-sup")
    return clear_page_url


def get_value_from_secret_file_json(key):
    cwd = os.getcwd()
    secret_file = os.path.join(cwd, 'configs', 'secret_creds.json')
    with open(secret_file, 'r') as json_file:
        data = json.load(json_file)

        if key in data:
            return data[key]
        else:
            return None
