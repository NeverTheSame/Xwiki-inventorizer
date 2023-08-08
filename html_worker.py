import json
import os
from datetime import datetime, timezone


def create_html_for_single_space(space_name, articles_json_file):
    """
    Create an HTML file containing the articles data in a given XWiki space.

    Args:
        space_name (str): The name of the XWiki space.
        articles_json_file (str): The path to the JSON file containing the articles data.

    Returns:
        str: The name of the created HTML file.

    Raises:
        FileNotFoundError: If the articles_json_file does not exist.
    """
    str_now = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    resulting_html = f"""<body>
        <h1>{space_name} articles space as of {str_now}</h1>
        <table>
            <tr>
                <th><b>Article</b></th>
                <th><b>Created</b></th>
                <th><b>Modified</b></th>
                <th><b>Modifier</b></th>
            </tr>
    """

    with open(articles_json_file, 'r') as f:
        articles_data = json.load(f)

    for article in articles_data:
        article_name = article[0]
        article_metadata = article[1]
        page_url = article_metadata['page_url']
        created = article_metadata['created']
        latest_modified = article_metadata['latest_modified']
        modifier = article_metadata['modifier_without_prefix']

        created_date = datetime.strptime(created, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
        latest_modified_date = datetime.strptime(latest_modified, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')

        resulting_html += f"""<tr>
            <td><a href="{page_url}">{article_name}</a></td>
            <td>{created_date}</td>
            <td>{latest_modified_date}</td>
            <td>{modifier}</td>
        </tr>
        """

    resulting_html += """
        </table>
    </body>
    """

    html_filename = f"articles_in_{space_name}_as_of_{str_now}.html"

    if not os.path.exists(html_filename):
        with open(html_filename, 'w') as f:
            f.write(resulting_html)
        print(f"Created HTML file: {html_filename}\n")
    else:
        print("HTML file already exists: " + html_filename)

    return html_filename
