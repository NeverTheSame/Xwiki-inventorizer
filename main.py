import sys
import unittest
from urllib.parse import urlparse

import requests
import json
import os
import warnings
import urllib3
import re

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

import xml.etree.ElementTree as ET

import markdown_worker


class XWikiAPIFetcher:
    def __init__(self):
        """
        Set up the required variables and configuration data.
        This function creates pointers to the necessary secret files, loads the required
        API secrets and sets the corresponding variables.

        Args:
            self (object): The object containing the setUp method

        Returns:
            None

        Raises:
            N/A
        """
        # create pointer to secret files
        cwd = os.getcwd()
        # parent_dir = os.path.abspath(os.path.join(cwd, os.pardir))
        # holds auth data
        self.secret_creds_file = os.path.join(cwd, 'secret_creds.json')
        # holds API elements data
        api_secret_file = os.path.join(cwd, 'api_secret.json')

        # load the JSON data
        with open(api_secret_file, 'r') as f:
            api_secrets = json.load(f)

        self.base_url = api_secrets["base_url"]
        self.main_url = api_secrets["bin"]["main_url"]
        self.internal_technical_docs_url = api_secrets["bin"]["internal_technical_docs_url"]
        self.vbm_url = api_secrets["bin"]["vbm_url"]
        self.vb365_main_space_url = api_secrets["rest"]["vb365_main_space_url"]
        self.gk_space_url = api_secrets["rest"]["gk_space_url"]
        self.test_page_in_gk_history_space_url = api_secrets["rest"]["test_page_in_gk_history_space_url"]
        self.gk_children_pages_url = api_secrets["rest"]["gk_children_pages_url"]
        self.how_to_children_pages_url = api_secrets["rest"]["how_to_children_pages_url"]

        self.bad_article_url = api_secrets["bin"]["bad_article_url"]
        self.ns = {'xwiki': 'http://www.xwiki.org'}

    def _send_authenticated_response(self, url):
        """
        Sends an authenticated GET request to the specified URL using the secret credentials
        loaded from the secret file, and returns the response object.

        Args:
            self (object): The object containing the _send_authenticated_response method
            url (str): The URL to which the authenticated GET request should be sent

        Returns:
            response (Response): A Response object containing the server's response to the request

        Raises:
            N/A
        """
        with open(self.secret_creds_file) as secret_file:
            data = json.load(secret_file)
        response = requests.get(url, data=data, verify=False)
        return response

    def suppress_insecure_and_resource_warnings(func):
        """
        A decorator function to suppress the insecure request warnings and resource warnings
        for a given function. This decorator is used to ignore warnings that might occur during
        the execution of a function.

        Args:
            func (function): The function to be decorated with this decorator

        Returns:
            wrapper (function): A function that suppresses insecure request warnings and resource warnings

        Raises:
            N/A
        """

        def wrapper(*args, **kwargs):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
                warnings.filterwarnings("ignore", category=ResourceWarning)
                return func(*args, **kwargs)

        return wrapper

    def _get_xml(self, url):
        """
        A helper function that sends an authenticated request to the specified URL and returns the XML text.

        Args:
            self: The object instance of the class
            url (str): The URL to which the authenticated request is to be sent.

        Returns:
            str: The XML text received from the server.

        Raises:
            None
        """
        response = self._send_authenticated_response(url)
        return response.text

    def _return_pages_list(self, url):
        """
        Retrieves a list of XWiki pages from the specified URL.

        Args:
            url (str): The URL of the XWiki page to retrieve.

        Returns:
            list: A list of pageSummary elements extracted from the XML response.

        Raises:
            None
        """
        text_to_parse = self._get_xml(url)
        root = ET.fromstring(text_to_parse)
        pages_list = []
        # iterate over each pageSummary element and extract the desired elements
        for page in root.findall('.//xwiki:pageSummary', self.ns):
            pages_list.append(page)
            title = page.find('xwiki:title', self.ns).text
            xwiki_relative_url = page.find('xwiki:xwikiRelativeUrl', self.ns).text

            # print the extracted elements
            print(f'Title: {title}')
            print(f'xwikiRelativeUrl: {xwiki_relative_url}\n')
        return pages_list

    def _create_articles_dictionaries_to_process(self, space_url):
        """
        Given a space URL, this function fetches the XML content using _get_xml method,
        processes it using ElementTree library, and returns a list of dictionaries
        containing article data for articles in the specified space URL.

        Args:
            self (object): The object containing the _create_articles_dictionaries_to_process method
            space_url (str): The URL of the XWiki space to be processed

        Returns:
            articles_dictionaries (list): A list of dictionaries containing article data for articles
            in the specified XWiki space URL. Each dictionary contains the following keys:
                - title (str): The title of the article
                - page_url (str): The URL of the article page
                - links (list): A list of dictionaries, where each dictionary represents a link in the article.
                  Each link dictionary contains the following keys:
                      - label (str): The label of the link
                      - url (str): The URL the link is pointing to

        Raises:
            N/A
        """
        text_to_parse = self._get_xml(space_url)
        root = ET.fromstring(text_to_parse)
        articles_dictionaries = []
        count = 0
        for page in root.findall('.//xwiki:pageSummary', self.ns):
            page_url = page.find('xwiki:xwikiRelativeUrl', self.ns).text

            if "/How-to/" in page_url:
                base_url, article_url_leaf = page_url.split("/How-to/", 1)
            elif "/General-Knowledge/" in page_url:
                base_url, article_url_leaf = page_url.split("/General-Knowledge/", 1)

            # problematic_units.json: article-with-%5B
            if "%5B" in article_url_leaf:
                print(f"Redirecting {page_url} \nto a different portal due to the restricted symbol\n")
                page_url = page_url.replace("xwiki", "xwiki-sup")

            # problematic_units.json: article-with-%3A
            if "%3A" in article_url_leaf:
                print(f"Skipping {page_url} due to the restricted symbols in URL")

            else:
                title = page.find('xwiki:title', self.ns).text
                links = page.findall('xwiki:link', self.ns)
                page_data = {'title': title, 'page_url': page_url, 'links': links}
                articles_dictionaries.append(page_data)

        print("Links are created")
        return articles_dictionaries

    def _fetch_and_process_xwiki_data(self, space_url):
        """
        Fetches metadata and historical data for all articles in the given XWiki space URL, and processes the data to
        print information about each article, including its creation date, last modified date, and modifier.
        The function returns a dictionary of article titles and their corresponding metadata, sorted by creation date.

        :param space_url: The URL of the XWiki space to fetch data from.
        :type space_url: str
        :return: A dictionary of article titles and their corresponding metadata, sorted by creation date.
        :rtype: dict
        """
        articles_in_space = {}
        dictionaries_of_articles = self._create_articles_dictionaries_to_process(space_url)

        for article_dict in dictionaries_of_articles:
            print(f"Processing {article_dict['page_url']}")
            if "xwiki-sup" in article_dict['page_url']:
                print(f"Skipping {article_dict['page_url']} due to the broken link")
            if "xwiki-sup" not in article_dict['page_url']:
                for link in article_dict["links"]:
                    href = link.get('href')
                    # find metadata page for an article
                    if re.search(r'pages/WebHome$', href):
                        metadata_text_to_parse = self._get_xml(href)
                        metadata_root = ET.fromstring(metadata_text_to_parse)
                        created = metadata_root.find('xwiki:created', self.ns).text
                    # find history page for an article
                    if "WebHome/history" in href:
                        modified_timestamps = []
                        hist_text_to_parse = self._get_xml(href)
                        history_root = ET.fromstring(hist_text_to_parse)
                        for history_record in history_root.findall('.//xwiki:historySummary', self.ns):
                            modified = history_record.find('xwiki:modified', self.ns).text
                            modified_timestamps.append(modified)
                            latest_modified = modified_timestamps[0]
                            modifier = history_record.find('xwiki:modifier', self.ns).text
                            modifier_without_prefix = modifier.replace("XWiki.", "").replace("xwiki:", "")
                        articles_in_space[article_dict["title"]] = (article_dict["page_url"],
                                                                  created,
                                                                  latest_modified,
                                                                  modifier_without_prefix)
        # Sort by created
        sorted_historical_data = sorted(articles_in_space.items(), key=lambda x: x[1][1], reverse=False)
        # for article in sorted_historical_data:
        #     article_name = article[0]
        #     article_url = article[1][0]
        #     creation_date = article[1][1]
        #     modified_date = article[1][2]
        #     modifier = article[1][3]
        #     print(f"Article [{article_name}]({article_url}) was created on **{creation_date}**. \n"
        #           f"It was last modified on **{modified_date}** by **{modifier}**\n")
        return sorted_historical_data

    def _fetch_and_process_xwiki_data_json(self, space_url):
        """
        Fetches metadata and historical data for all articles in the given XWiki space URL, and processes the data to
        print information about each article, including its creation date, last modified date, and modifier.
        The function returns a JSON object of article titles and their corresponding metadata, sorted by creation date.

        :param space_url: The URL of the XWiki space to fetch data from.
        :type space_url: str
        :return: A JSON object of article titles and their corresponding metadata, sorted by creation date.
        :rtype: str
        """
        articles_in_space = {}
        dictionaries_of_articles = self._create_articles_dictionaries_to_process(space_url)
        for article_dict in dictionaries_of_articles:
            print(f"Processing {article_dict['page_url']}")
            if "xwiki-sup" in article_dict['page_url']:
                print(f"Skipping {article_dict['page_url']} due to the broken link")
            if "xwiki-sup" not in article_dict['page_url']:
                for link in article_dict["links"]:
                    href = link.get('href')
                    # find metadata page for an article
                    if re.search(r'pages/WebHome$', href):
                        metadata_text_to_parse = self._get_xml(href)
                        metadata_root = ET.fromstring(metadata_text_to_parse)
                        created = metadata_root.find('xwiki:created', self.ns).text
                    # find history page for an article
                    if "WebHome/history" in href:
                        modified_timestamps = []
                        hist_text_to_parse = self._get_xml(href)
                        history_root = ET.fromstring(hist_text_to_parse)
                        for history_record in history_root.findall('.//xwiki:historySummary', self.ns):
                            modified = history_record.find('xwiki:modified', self.ns).text
                            modified_timestamps.append(modified)
                            latest_modified = modified_timestamps[0]
                            modifier = history_record.find('xwiki:modifier', self.ns).text
                            modifier_without_prefix = modifier.replace("XWiki.", "").replace("xwiki:", "")
                        articles_in_space[article_dict["title"]] = {"page_url": article_dict["page_url"],
                                                                    "created": created,
                                                                    "latest_modified": latest_modified,
                                                                    "modifier_without_prefix": modifier_without_prefix}
        # Sort by created
        sorted_historical_data = sorted(articles_in_space.items(), key=lambda x: x[1]["created"], reverse=False)
        return sorted_historical_data

    @suppress_insecure_and_resource_warnings
    def inventory_vb365_gk_pages(self):
        """
        This function prints the processed data for the 'General Knowledge' children pages in the vb365 space.
        """
        return self._fetch_and_process_xwiki_data_json(self.gk_children_pages_url)

    @suppress_insecure_and_resource_warnings
    def inventory_vb365_how_to_pages(self):
        """
        This function prints the processed data for the 'How-to' children pages in the vb365 space.
        """
        return self._fetch_and_process_xwiki_data_json(self.how_to_children_pages_url)



def main():
    articles_in_how_to_space = XWikiAPIFetcher().inventory_vb365_how_to_pages()
    articles_json_file = markdown_worker.create_articles_json_file("how-to", articles_in_how_to_space)
    markdown_worker.create_md("how-to", articles_json_file)

    articles_in_gk_space = XWikiAPIFetcher().inventory_vb365_gk_pages()
    gk_articles_json_file = markdown_worker.create_articles_json_file("general-knowledge", articles_in_gk_space)
    markdown_worker.create_md("general-knowledge", gk_articles_json_file)


if __name__ == '__main__':
    main()
