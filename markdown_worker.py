import json
import os
from datetime import datetime, timezone


def create_articles_json_file(space_name, list_of_articles):
    """
    Given a space name and a list of articles, creates a JSON file with the current date and time
    as part of the filename and writes the list of articles to the file. If a file with the same name
    already exists, the function will use the existing file and return its name.

    Args:
        space_name (str): The name of the XWiki space.
        list_of_articles (list): A list of dictionaries representing articles in the space.

    Returns:
        str: The name of the created or existing JSON file.
    """
    str_now = datetime.now(timezone.utc).strftime("%m_%d_%Y")
    temp_file_name = f"articles_in_{space_name}_space_as_of_{str_now}.json"

    output_file_name = None  # define the variable before the if statement
    if not os.path.exists(temp_file_name):
        with open(temp_file_name, 'w') as output_file:
            json.dump(list_of_articles, output_file)
        print("Created json file: " + temp_file_name)
        output_file_name = output_file.name
    else:
        print("File already exists: " + temp_file_name)
        # set output_file_name to the existing file name
        output_file_name = temp_file_name
    return output_file_name


def create_md(space_name, articles_json_file):
    """
    Create a markdown file containing the articles data in a given XWiki space.

    Args:
        space_name (str): The name of the XWiki space.
        articles_json_file (str): The path to the JSON file containing the articles data.

    Returns:
        str: The name of the created markdown file.

    Raises:
        FileNotFoundError: If the articles_json_file does not exist.
    """
    str_now = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    resulting_md = f"Xwiki articles in <b>{space_name}<b> space as of {str_now}:\n"
    resulting_md = resulting_md + ' | <b>Article</b> | <b>Created</b> | <b>Modified</b> | <b>Modifier</b> |\n'
    resulting_md = resulting_md + ' | ---- | ------ | ---- | ---- |\n'

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

        resulting_md = resulting_md + f" | [{article_name}]({page_url}) | {created_date}" \
                                      f" | {latest_modified_date}" \
                                      f" | {modifier} |\n"


    md_filename = f"articles_in_{space_name}_as_of{str_now}.md"

    if not os.path.exists(md_filename):
        with open(md_filename, 'w') as f:
            f.write(resulting_md)
        print(f"Created md file: {md_filename}\n")
    else:
        print("Md already exists: " + md_filename)

    return resulting_md
