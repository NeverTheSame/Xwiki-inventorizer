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


def _extract_title_from_url(link):
    """
    Extracts the title from a URL contained in a link HTML element.

    Args:
        link (bs4.element.Tag): The link HTML element to extract the title from.

    Returns:
        str: The title extracted from the URL.
    """
    # Parse the URL to get the path
    path = urlparse(link.attrs['href']).path
    # Split the path into parts using "/"
    parts = path.split('/')
    # Get the last part of the path
    title = parts[-2]
    # For situation when URL has double "/" at the end
    if title == '/':
        title = parts[-3]
    return title


# region Not used class that utilizes Soup
class TestWebPageFetchWithSoup(unittest.TestCase):
    # create pointer to secret files
    cwd = os.getcwd()
    parent_dir = os.path.abspath(os.path.join(cwd, os.pardir))
    # holds auth data
    secret_creds_file = os.path.join(parent_dir, 'configs', 'secret_creds.json')
    # holds API elements data
    api_secret_file = os.path.join(parent_dir, 'configs', 'api_secret.json')

    # load the JSON data
    with open(api_secret_file, 'r') as f:
        api_secrets = json.load(f)

    base_url = api_secrets["base_url"]
    main_url = api_secrets["bin"]["main_url"]
    internal_technical_docs_url = api_secrets["bin"]["internal_technical_docs_url"]
    vbm_url = api_secrets["bin"]["vbm_url"]
    general_knowledge_url = api_secrets["bin"]["general_knowledge_url"]

    def _send_authenticated_response(self, url):
        with open(self.secret_creds_file) as secret_file:
            data = json.load(secret_file)
        response = requests.get(url, data=data, verify=False)
        return response

    def test_fetch_web_page_url(self):
        response = self._send_authenticated_response(self.main_url)
        self.assertEqual(response.status_code, 200)

    def test_fetch_all_links_in_vbm(self):
        response = self._send_authenticated_response(self.vbm_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')

        self.assertEqual(len(links), 56)

    def test_fetch_first_links_in_vbm_general_knowledge(self):
        """ Test that all 32 articles in General Knowledge are present
            Confirmation is done by manually checking number of articles in Tree"""
        response = self._send_authenticated_response(self.general_knowledge_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')
        general_knowledge_links = []
        for link in links:
            if 'href' in link.attrs:
                if 'General-Knowledge' in link.attrs['href']:
                    if link.attrs['href'].startswith(self.main_url):
                        print(link.attrs['href'])
                        general_knowledge_links.append(link.attrs['href'])
        self.assertEqual(len(general_knowledge_links), 32)

    def test_fetch_children_class_links_in_general_knowledge(self):
        response = self._send_authenticated_response(self.general_knowledge_url)

        soup = BeautifulSoup(response.text, 'html.parser')
        children_div = soup.find('div', class_='children')
        child_pages = []
        for link in children_div.find_all('a'):
            child_pages.append(link['href'])
        self.assertEqual(len(child_pages), 32)

    def test_fetch_all_links_in_vbm_general_knowledge_with_selenium(self):
        # Selenium setup
        # Set desired capabilities for the Chrome browser
        caps = DesiredCapabilities.CHROME.copy()
        caps['acceptInsecureCerts'] = True
        driver = webdriver.Chrome(desired_capabilities=caps)
        driver.get(self.general_knowledge_url)

        gk_pagination = self.api_secrets["elements"]["gk_pagination"]

        show_more_link = WebDriverWait(driver, 5) \
            .until(EC.presence_of_element_located((By.ID, f"{gk_pagination}")))
        show_more_link.click()

        # Get the updated HTML source code
        gen_knowledge_with_links_extended_html = driver.page_source

        # Web scraping part
        soup = BeautifulSoup(gen_knowledge_with_links_extended_html, 'html.parser')
        links = soup.find_all('a')
        general_knowledge_links = []
        for link in links:
            if 'id' in link.attrs:
                print(link.attrs['id'])
            if 'href' in link.attrs:
                if 'General-Knowledge' in link.attrs['href']:
                    if link.attrs['href'].startswith(self.main_url):
                        title = _extract_title_from_url(link)
                        general_knowledge_links.append(title)
        self.assertEqual(len(general_knowledge_links), 32)
# endregion


class TestWebPageFetchWithApi(unittest.TestCase):
    def setUp(self):
        """
        Set up the required variables and configuration data for the tests to run.
        This function creates pointers to the necessary secret files, loads the required
        API secrets and sets the corresponding variables for the test run.

        Args:
            self (object): The object containing the setUp method

        Returns:
            None

        Raises:
            N/A
        """
        # create pointer to secret files
        cwd = os.getcwd()
        parent_dir = os.path.abspath(os.path.join(cwd, os.pardir))
        # holds auth data
        self.secret_creds_file = os.path.join(parent_dir, 'configs', 'secret_creds.json')
        # holds API elements data
        api_secret_file = os.path.join(parent_dir, 'configs', 'api_secret.json')

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

    @suppress_insecure_and_resource_warnings
    def test_fetch_from_vbm_main_success(self):
        """
        A unit test function to test the success of fetching data from the VBM main space URL
        using an authenticated response.

        Args:
            self: The object instance of the test case

        Returns:
            None

        Raises:
            AssertionError: If the response status code is not equal to 200 (OK)
        """
        url = f"{self.vb365_main_space_url}"
        response = self._send_authenticated_response(url)
        self.assertEqual(response.status_code, 200)

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

    @suppress_insecure_and_resource_warnings
    def test_there_are_only_7_pages_in_main(self):
        """
        Test if there are only 7 pages in the main space.

        Returns:
            None

        Raises:
            AssertionError: If the number of pages in the main space is not equal to 7.
        """
        pages_in_main = self._return_pages_list(self.vb365_main_space_url)
        self.assertEqual(len(pages_in_main), 7)

    @suppress_insecure_and_resource_warnings
    def test_general_knowledge_pages(self):
        """
        Test whether the _return_pages_list function correctly extracts information about the pages in the General
        Knowledge (GK) space of the API. It first calls _return_pages_list with the URL of the GK space, which returns
        a list of pages and prints information about each page, including its title and XWiki relative URL. The function
        then asserts that the length of the returned list is equal to 35, which is the expected number of pages in the
        GK space.
        """
        pages_in_gk = self._return_pages_list(self.gk_space_url)
        self.assertEqual(len(pages_in_gk), 35)

    @suppress_insecure_and_resource_warnings
    def test_general_knowledge_history(self):
        """
        Test the General Knowledge history by retrieving the modified timestamps for the test page.

        Retrieves the XML data from the General Knowledge history page for a test page, and extracts the modified
        timestamp for each page summary element. The function then evaluates whether the length of modified timestamps
        is greater than one and not empty. Prints the first modified timestamp to the console.

        Raises:
            AssertionError: if the length of modified timestamps is less than or equal to one, or if the data returned
                is empty.
        """
        text_to_parse = self._get_xml(self.test_page_in_gk_history_space_url)
        root = ET.fromstring(text_to_parse)

        modified_timestamps = []
        # iterate over each pageSummary element and extract the desired elements
        for page in root.findall('.//xwiki:historySummary', self.ns):
            modified = page.find('xwiki:modified', self.ns).text
            modified_timestamps.append(modified)
        print(f'modified: {modified_timestamps[0]}')

        # evaluate modified_timestamps data returned is not empty and is more than one
        self.assertTrue(len(modified_timestamps) > 1)

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
        historical_data = {}
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
                        historical_data[article_dict["title"]] = (article_dict["page_url"],
                                                                  created,
                                                                  latest_modified,
                                                                  modifier_without_prefix)
        # Sort by created
        sorted__historical_data = sorted(historical_data.items(), key=lambda x: x[1][1], reverse=False)
        for article in sorted__historical_data:
            article_name = article[0]
            article_url = article[1][0]
            creation_date = article[1][1]
            modified_date = article[1][2]
            modifier = article[1][3]
            print(f"Article [{article_name}]({article_url}) was created on **{creation_date}**. \n"
                  f"It was last modified on **{modified_date}** by **{modifier}**\n")
        return historical_data

    @suppress_insecure_and_resource_warnings
    def test_vb365_gk_pages(self):
        """
        This function tests the _fetch_and_process_xwiki_data method by verifying that the number of processed pages
        from the VB365 General Knowledge space is equal to 35. It accomplishes this by calling
        _fetch_and_process_xwiki_data with the URL of the space containing the General Knowledge pages and then
        asserting that the length of the dictionary returned by the function is 35.
        """
        historical_data = self._fetch_and_process_xwiki_data(self.gk_children_pages_url)
        self.assertEqual(len(historical_data), 35)

    @suppress_insecure_and_resource_warnings
    def test_vb365_how_to_pages(self):
        """
        Test function to fetch and process historical data for the 'How-To' children pages in the vb365 space.
        It fetches the historical data for each article, sorts it by created date and prints the processed data.

        Args:
            self: The object itself.

        Returns:
            None. Asserts that the length of the processed data dictionary is equal to 27.
        """

        historical_data = self._fetch_and_process_xwiki_data(self.how_to_children_pages_url)
        self.assertEqual(len(historical_data), 27)


if __name__ == '__main__':
    unittest.main()
