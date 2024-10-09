import logging
import requests
import jsonify
import json
import datetime
import argparse
from argparse import RawTextHelpFormatter
from modules.confluance import ConfluanceApiClient

def comma_separated_list(arg):
    return arg.split(',')

def generate_log_filename():
    current_date = datetime.datetime.now()
    date_str = "{0}_{1}".format(current_date.strftime('%s'), current_date.strftime('%d%m%y'))
    filename = f"{date_str}_confluance.log"
    return filename

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
    parser.add_argument("--logfile", help="File to log to, default logfile 'DATEFORMAT_confluance.log'", default=f"{generate_log_filename()}")
    parser.add_argument("--proxy", help="Set a proxy", default=None)
    parser.epilog="""
    Examples:
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-spaces
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword wachtwoord
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword wachtwoord --space IT
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --sa --ext pdf,docx,txt,kdb
        python3 confugrind.py https://some-confluance.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --sa --space IT --ext pdf,docx,txt,kdb
    """

    args = parser.parse_args()

    #setup logging
    logging.basicConfig(level=logging.INFO,
                        format='%(message)s',
                        handlers=[
                            logging.FileHandler(args.logfile),
                            logging.StreamHandler()
                        ])
    
    #setup the client
    client = ConfluanceApiClient(args.baseurl, args.token, args.proxy)

    #search attachments by space, with extensions
    if args.sa:
        #if not args.space or not args.ext:
        if not args.ext:
            parser.error("--sa requires --space and --ext options")

        if args.space:
            client.list_attachments_by_space(args.space, args.ext)
        else:
            client.list_attachments_all(args.ext)
        #client.list_attachments_by_space(args.space, args.ext)

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
    try:
        main()
    except Exception as e:
        print(F"An error occurred: {e}")