import requests
import json
import urllib3
import re
import logging
from bs4 import BeautifulSoup
from colorama import init, Fore, Back, Style
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

class ConfluanceApiClient:
    def __init__(self, baseurl, token, proxy):
        self.url = baseurl
        self.token = token
        self.proxy = {
            "http": proxy,
            "https": proxy
        }
        self.headers = {
            "Authorization": f"Bearer {token}" 
        }
        self.r = requests.session()
        logging.info("Initialized ConfluenceApiClient")
    
    def search_api(self, keyword):
        try:
            response = self.r.get(f'{self.url}/rest/api/content/search?cql=text+~+"{keyword}"&limit=1000', headers=self.headers, proxies=self.proxy, verify=False)
            pages = self.create_dict_from_search(response.json())
            return pages

        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"
        
    def search_api_by_space(self, space, keyword):
        try:
            response = self.r.get(f'{self.url}/rest/api/content/search?cql=space+=+{space}+and+text+~+"{keyword}"&limit=1000', headers=self.headers, proxies=self.proxy, verify=False)
            pages = self.create_dict_from_search(response.json())
            return pages

        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"       
        
    def create_dict_from_search(self, data):
        pages = {}
        for page in data["results"]:
            pages[page["id"]] = {"title": page["title"], "_links": page["_links"]}
        return pages
    
    def grep_content_page(self, data, keyword):
        pattern = rf'^.*(?:{keyword}).*$'
        try:
            #   key, value
            for page_id, page_info in data.items():
                if "_links" in page_info:
                    response = self.r.get(f'{page_info["_links"]["self"]}?expand=body.view', headers=self.headers, proxies=self.proxy, verify=False)
                    pageBody = response.json()["body"]["view"]["value"]
                    soup = BeautifulSoup(pageBody, 'html.parser')
                    pretty_html = soup.prettify()
                    matches = re.findall(pattern, pretty_html, re.MULTILINE)
                    if matches:
                        for match in matches:
                            logging.info(Fore.GREEN + f'\nMatch found in:' + Style.RESET_ALL)
                            logging.info(f'{page_info["_links"]["self"]}\n{self.url}{page_info["_links"]["webui"]}\n\n{match}')

        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"
        
    def list_spaces(self):
        try:
            response = self.r.get(f"{self.url}/rest/api/space?limit=1000", headers=self.headers, proxies=self.proxy, verify=False)
            data = response.json()
            spaces = {}
            for space in data["results"]:
                spaces[space["id"]] = {
                    "key": space["key"],
                    "name": space["name"],
                    "_links": space["_links"]
                }
            logging.info(json.dumps(spaces, indent=4))
            return spaces 
        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"         


    def list_pages_by_space(self, key):
        try:
            response = self.r.get(f"{self.url}/rest/api/content?spaceKey={key}&limit=1000", headers=self.headers, proxies=self.proxy, verify=False)
            data = response.json()
            pages = {}
            for page in data["results"]:
                pages[page["id"]] = {"title": page["title"], "_links": page["_links"]}
            return pages

        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"  

    def list_attachments(self, page_id, page_title, page_url, ext=None):
        try:
            response = self.r.get(f"{self.url}/rest/api/content/{page_id}/child/attachment", headers=self.headers, proxies=self.proxy, verify=False)
            data = response.json()["results"]

            attachments = []
            for attachment in data:
                extension = attachment["extensions"]["mediaType"].split('/')[-1]
                if extension.lower() in ext:
                    attachment_info = {
                        "title": attachment["title"],
                        "url": self.url + attachment["_links"]["download"]
                    }
                    attachments.append(attachment_info)
            return attachments

        except requests.exceptions.HTTPError as http_err:
            logging.info(f"HTTP Error occurred: {http_err}")
            return []
        except requests.exceptions.RequestException as err:
            logging.info(f"Error occurred: {err}")
            return []
        
    def list_attachments_by_space(self, space, ext):
        pages = self.list_pages_by_space(space)
        for page_id, page_info in pages.items():
            attachments = self.list_attachments(page_id, page_info["title"], self.url + page_info["_links"]["webui"], ext)
            for attachment in attachments:
                logging.info(f"\nPage name: {page_info['title']}\nURL: {self.url + page_info['_links']['webui']}")
                logging.info(f"Attachment: {attachment['title']}\nURL: {attachment['url']}\n")                
                        
    def search_keywords_on_pages(self, keyword, space=None):
        if space:
            pages = self.search_api_by_space(space, keyword)
        else:
            pages = self.search_api(keyword)
        self.grep_content_page(pages, keyword)
        



