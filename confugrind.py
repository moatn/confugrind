import requests
import jsonify
import json
import argparse
from argparse import RawTextHelpFormatter
from modules.confluance import ConfluanceApiClient

def comma_separated_list(arg):
    return arg.split(',')

def main():
    parser = argparse.ArgumentParser(description="Confluance API client/ scraper", formatter_class=RawTextHelpFormatter)
    parser.add_argument("baseurl", help="Baseurl of the Confluance instance")
    parser.add_argument("token", help="Token created for querying the REST api")
    parser.add_argument("--keyword", help="Keyword to search for")
    parser.add_argument("--space", help="Space key")
    parser.add_argument("--ext", type=comma_separated_list, help="comma seperated extensions to look for on pages")
    parser.add_argument("--sa", action="store_true", help="search attachments, keyword is also needed for this param")
    parser.add_argument("--search", action="store_true", help="Search confluance trough CQL queries")
    parser.add_argument("--list-spaces", action="store_true", help="List all spaces and keys")
    parser.epilog="""\
    Examples:
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-spaces
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword wachtwoord
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword wachtwoord --space IT
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --sa --space IT --ext pdf,docx,txt,kdb
    """
    args = parser.parse_args()
    client = ConfluanceApiClient(args.baseurl, args.token)

    
    #search attachments by space, with extensions
    if args.sa:
        if not args.space or not args.ext:
            parser.error("--sa requires --space and --ext options")
        client.list_attachments_by_space(args.space, args.ext)

    #search confluance for keywords. 
    if args.search and args.keyword:
        if args.space:
            client.search_keywords_on_pages(args.keyword, args.space)
        else:
            client.search_keywords_on_pages(args.keyword)

    #just list all the pages
    if args.list_spaces:
        client.list_spaces()


if __name__ == "__main__":
    main()