import json
import os
import re
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import urllib3

import html_worker
import markdown_worker
import utilities
from utilities import transform_datetime
from utilities import get_value_from_secret_file_json


def process_space(pages_url, space_name):
    """
    This function calls two functions from the XWikiAPIFetcher and markdown_worker classes to process the XWiki data
    and create markdown files for a given space.

    Arguments:
    pages_url (string): the URL of the XWiki space to process.
    space_name (string): the name of the space to be created.

    Returns:
    This function does not return anything. Instead, it calls two functions:
    """
    articles_in_space = XWikiAPIFetcher().fetch_and_process_xwiki_data(pages_url)
    articles_json_file = markdown_worker.create_articles_json_file(space_name, articles_in_space)
    markdown_worker.create_md(space_name, articles_json_file)
    html_worker.create_html_for_single_space(space_name, articles_json_file)


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

        # holds auth data
        self.secret_creds_file = os.path.join(cwd, 'configs', 'secret_creds.json')
        # holds API elements data
        api_secret_file = os.path.join(cwd, 'configs', 'api_secret.json')
        # holds resulting HTML file
        self.html_file = os.path.join(cwd, 'outputs', 'articles_in_all_spaces.html')

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
        self.configure_children_pages_url = api_secrets["rest"]["configure_children_pages_url"]
        self.inventory_resulting_article = api_secrets["rest"]["inventory_resulting_article"]

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
        Returns a list of page summaries for a given XWiki URL.

        Parameters:
        url (str): The URL of the XWiki instance.

        Returns:
        pages_list (list): A list of page summaries, each of which is represented as an Element object.

        Raises:
        None.

        Usage:
        pages_list = _return_pages_list('https://myxwiki.org')
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

    def _create_articles_dictionaries_to_process(self, space_url) -> list:
        """
        Returns a list of dictionaries, where each dictionary represents a page in a given XWiki space.

        Parameters:
        space_url (str): The URL of the XWiki space to process.

        Returns:
        articles_dictionaries (list): A list of dictionaries, where each dictionary contains information about a page,
        including its title, URL, and links.

        Raises:
        None.

        Usage:
        articles_dictionaries = _create_articles_dictionaries_to_process('https://myxwiki.org/spaces/MySpace')
        """
        text_to_parse = self._get_xml(space_url)
        root = ET.fromstring(text_to_parse)
        articles_list = []
        for page in root.findall('.//xwiki:pageSummary', self.ns):
            page_url = page.find('xwiki:xwikiRelativeUrl', self.ns).text

            if "/How-to/" in page_url:
                base_url, article_url_leaf = page_url.split("/How-to/", 1)
            elif "/General-Knowledge/" in page_url:
                base_url, article_url_leaf = page_url.split("/General-Knowledge/", 1)
            elif "/How-to-configure-VBO365/" in page_url:
                base_url, article_url_leaf = page_url.split("/How-to-configure-VBO365/", 1)
            elif "/Patch-notes/" in page_url:
                base_url, article_url_leaf = page_url.split("/Patch-notes/", 1)

            # problematic_units.json: article-with-%5B
            if "%5B" in article_url_leaf:
                print(f"Skipping {page_url} due to the restricted symbols in URL")
                page_url = page_url.replace("xwiki", "xwiki-sup")

            # problematic_units.json: article-with-%3A
            if "%3A" in article_url_leaf:
                print(f"Skipping {page_url} due to the restricted symbols in URL")
                page_url = page_url.replace("xwiki", "xwiki-sup")

            # problematic_units.json: article-with-%60
            if "%60" in article_url_leaf:
                print(f"Skipping {page_url} due to the restricted symbols in URL")
                page_url = page_url.replace("xwiki", "xwiki-sup")

            else:
                title = page.find('xwiki:title', self.ns).text
                links = page.findall('xwiki:link', self.ns)
                page_data = {'title': title, 'page_url': page_url, 'links': links}
                articles_list.append(page_data)

        print(f"Links for {space_url} are created")
        return articles_list

    @suppress_insecure_and_resource_warnings
    def fetch_and_process_xwiki_data(self, space_url) -> list:
        """
        Fetches XWiki data from the given space URL and processes it into a JSON object.

        Args:
            space_url (str): The URL of the XWiki space to fetch data from.

        Returns:
            A sorted list of dictionaries containing historical data for each article in the XWiki space.
            Each dictionary contains the following keys:
            - title: The title of the article.
            - page_url: The URL of the article.
            - created: The timestamp of when the article was created.
            - latest_modified: The timestamp of the latest modification made to the article.
            - modifier_without_prefix: The name of the user who made the latest modification to the article, without the
                                        "XWiki." or "xwiki:" prefix.
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
    def create_html_for_all_spaces(self):
        list_of_urls = [self.gk_children_pages_url, self.how_to_children_pages_url,
                        self.configure_children_pages_url]
        dictionary_of_all_articles = {}
        resulting_html = r"""
        <style>
            table {
                border-collapse: separate;
                border-spacing: 1px;
            }
        
            table th, table td {
                border: 1px solid #999999;
                padding: 5px;
            }
        </style>
        <body>
        """
        str_now = datetime.now(timezone.utc).strftime("%Y_%m_%d")
        for urL_space in list_of_urls:
            # extract space name from URL
            parsed_url = urlparse(urL_space)
            # Extract the path and split it into segments
            path_segments = parsed_url.path.split('/')
            # Find the namespace segment
            namespace_segment = path_segments[-4]
            space_name = namespace_segment.replace('-', ' ')

            articles = self.fetch_and_process_xwiki_data(urL_space)
            resulting_html += f"""<h1>Articles in {space_name} space as of {transform_datetime(str_now)}</h1>
                <table>
                    <tr>
                        <th><b>Article</b></th>
                        <th><b>Created</b></th>
                        <th><b>Modified</b></th>
                        <th><b>Modifier</b></th>
                    </tr>
                """
            for article in articles:
                resulting_html += f"""<tr>
                        <td><a href="{article[1]['page_url']}">{article[0]}</a></td>
                        <td>{transform_datetime(article[1]['created'])}</td>
                        <td>{transform_datetime(article[1]['latest_modified'])}</td>
                        <td>{article[1]['modifier_without_prefix']}</td>
                    </tr>
                """
            resulting_html += "</table>"
        resulting_html += "</body>"
        html_filename = f"outputs/articles_in_all_spaces.html"
        if not os.path.exists(html_filename):
            with open(html_filename, 'w') as f:
                f.write(resulting_html)
            print(f"Created HTML file: {html_filename}\n")
        else:
            print("HTML file already exists: " + html_filename)

        return html_filename

    @suppress_insecure_and_resource_warnings
    def update_article(self, article_url):
        headers = {
            'Content-Type': 'text/plain',
            'Authorization': f"{get_value_from_secret_file_json('bearer_token')}"
        }

        if os.path.exists(self.html_file):
            with open(self.html_file, 'r') as f:
                data = "{{html}}"
                data += f.read()
                data += "{{/html}}"
            response = requests.put(article_url, headers=headers, data=data, verify=False)

            if response.status_code == 202:
                print('Page updated successfully.')
                self._clean_up()
            else:
                print(f'Failed to update page. Status code: {response.status_code}')
                print('Response content:', response.content)

    def _clean_up(self):
        """Adds timestamp to HTML file and renames it so that it is not used for the next update"""
        try:
            self.html_file = self.html_file.replace(".html",
                                                    f"_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.html")
            os.rename("outputs/articles_in_all_spaces.html", self.html_file)
            print(f"Renamed HTML file to {self.html_file}")
        except Exception as e:
            print("Failed to rename HTML file")


def main():
    xwiki_fetcher = XWikiAPIFetcher()
    xwiki_fetcher.create_html_for_all_spaces()
    html_article = xwiki_fetcher.inventory_resulting_article
    xwiki_fetcher.update_article(html_article)


if __name__ == '__main__':
    main()
