import requests
import json
import urllib3
import re
import logging
import os
import fnmatch
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)


class C:
    BOLD   = "\033[1m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    GREY   = "\033[90m"
    RED    = "\033[91m"
    RESET  = "\033[0m"

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

    def sanitize_filename(self, value):
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", value).strip().strip(".")
        if not cleaned:
            return "untitled"
        return cleaned[:150]

    def unique_filepath(self, directory, filename):
        base, ext = os.path.splitext(filename)
        candidate = filename
        counter = 1
        while os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{base}_{counter}{ext}"
            counter += 1
        return os.path.join(directory, candidate)

    def download_attachment_file(self, url, output_path):
        response = self.r.get(url, headers=self.headers, proxies=self.proxy, verify=False, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)

    def download_page_and_attachments(self, page_id, page_info, page_body, output_dir):
        page_title = page_info.get("title", page_id)
        page_folder_name = f"{page_id}_{self.sanitize_filename(page_title)}"
        page_folder_path = os.path.join(output_dir, page_folder_name)
        attachments_folder_path = os.path.join(page_folder_path, "attachments")
        os.makedirs(attachments_folder_path, exist_ok=True)

        page_html_path = os.path.join(page_folder_path, "page.html")
        with open(page_html_path, "w", encoding="utf-8") as html_file:
            html_file.write(page_body)
        logging.info(f"Saved page: {page_html_path}")

        attachments = self.list_attachments(page_id, page_title, self.url + page_info["_links"]["webui"])
        for attachment in attachments:
            safe_name = self.sanitize_filename(attachment["title"])
            attachment_path = self.unique_filepath(attachments_folder_path, safe_name)
            try:
                self.download_attachment_file(attachment["url"], attachment_path)
                logging.info(f"Saved attachment: {attachment_path}")
            except requests.exceptions.RequestException as err:
                logging.info(f"Failed to download attachment '{attachment['title']}': {err}")
    
    def grep_content_page(self, data, keyword, download_dir=None):
        pattern = rf'^.*(?:{re.escape(keyword)}).*$'
        try:
            #   key, value
            for page_id, page_info in data.items():
                if "_links" in page_info:
                    response = self.r.get(f'{page_info["_links"]["self"]}?expand=body.view', headers=self.headers, proxies=self.proxy, verify=False)
                    pageBody = response.json()["body"]["view"]["value"]
                    soup = BeautifulSoup(pageBody, 'html.parser')
                    pretty_html = soup.prettify()
                    matches = re.findall(pattern, pretty_html, re.MULTILINE | re.IGNORECASE)
                    if matches:
                        for match in matches:
                            logging.info(f'{C.GREEN}[+] Match found in:{C.RESET}')
                            logging.info(f'{C.CYAN}[Page]{C.RESET} {page_info["_links"]["self"]}')
                            logging.info(f'{C.GREY}[URL]  {self.url}{page_info["_links"]["webui"]}{C.RESET}')
                            logging.info(f'{C.YELLOW}[Hit]{C.RESET}  {match}')
                    if download_dir:
                        self.download_page_and_attachments(page_id, page_info, pageBody, download_dir)

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
            logging.info(f'\n{C.BOLD}[*] Spaces found:{C.RESET}')
            for sid, s in spaces.items():
                logging.info(f'  {C.CYAN}[Space]{C.RESET} {s["name"]}  {C.YELLOW}[Key]{C.RESET} {s["key"]}')
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

            allowed_extensions = None
            if ext:
                allowed_extensions = {extension.lower() for extension in ext}

            attachments = []
            for attachment in data:
                extension = attachment["extensions"]["mediaType"].split('/')[-1]
                if allowed_extensions and extension.lower() not in allowed_extensions:
                    continue
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
    
    def list_attachments_all(self, ext):
        spaces = self.list_spaces()
        for space_id, space_details in spaces.items():
            key = space_details.get("key")
            if key:
                pages = self.list_pages_by_space(key)
                for page_id, page_info in pages.items():
                    attachments = self.list_attachments(page_id, page_info["title"], self.url + page_info["_links"]["webui"], ext)
                    for attachment in attachments:
                        logging.info(f'\n  {C.CYAN}{page_info["title"]}{C.RESET}')
                        logging.info(f'  {C.GREY}{self.url + page_info["_links"]["webui"]}{C.RESET}')
                        logging.info(f'    {C.YELLOW}[Attachment]{C.RESET} {attachment["title"]}')
                        logging.info(f'    {C.GREY}{attachment["url"]}{C.RESET}')

    def list_attachments_by_space(self, space, ext):
        pages = self.list_pages_by_space(space)
        for page_id, page_info in pages.items():
            attachments = self.list_attachments(page_id, page_info["title"], self.url + page_info["_links"]["webui"], ext)
            for attachment in attachments:
                logging.info(f'\n  {C.CYAN}{page_info["title"]}{C.RESET}')
                logging.info(f'  {C.GREY}{self.url + page_info["_links"]["webui"]}{C.RESET}')
                logging.info(f'    {C.YELLOW}[Attachment]{C.RESET} {attachment["title"]}')
                logging.info(f'    {C.GREY}{attachment["url"]}{C.RESET}')

    def _matches_name_filter(self, title, include, exclude):
        name = title.lower()
        if include and not any(fnmatch.fnmatch(name, p.lower()) for p in include):
            return False
        if exclude and any(fnmatch.fnmatch(name, p.lower()) for p in exclude):
            return False
        return True

    def list_all_attachments_in_space(self, space, include=None, exclude=None, output_dir=None):
        logging.info(f'\n{C.BOLD}Listing all attachments in space: {space}{C.RESET}')
        if include:
            logging.info(f'  {C.GREY}include: {", ".join(include)}{C.RESET}')
        if exclude:
            logging.info(f'  {C.GREY}exclude: {", ".join(exclude)}{C.RESET}')
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            logging.info(f'  {C.GREY}output:  {os.path.abspath(output_dir)}{C.RESET}')

        pages = self.list_pages_by_space(space)
        if not pages:
            logging.info(f'  {C.RED}x No pages found in space \'{space}\'{C.RESET}')
            return

        total = 0
        for page_id, page_info in pages.items():
            attachments = self.list_attachments(page_id, page_info["title"], self.url + page_info["_links"]["webui"])
            filtered = [a for a in attachments if self._matches_name_filter(a["title"], include, exclude)]
            if filtered:
                logging.info(f'\n  {C.CYAN}{page_info["title"]}{C.RESET}')
                logging.info(f'  {C.GREY}{self.url + page_info["_links"]["webui"]}{C.RESET}')

                if output_dir:
                    page_folder = os.path.join(output_dir, f"{page_id}_{self.sanitize_filename(page_info['title'])}", "attachments")
                    os.makedirs(page_folder, exist_ok=True)

                for attachment in filtered:
                    logging.info(f'    {C.YELLOW}[Attachment]{C.RESET} {attachment["title"]}')
                    logging.info(f'    {C.GREY}{attachment["url"]}{C.RESET}')
                    if output_dir:
                        dest = self.unique_filepath(page_folder, self.sanitize_filename(attachment["title"]))
                        try:
                            self.download_attachment_file(attachment["url"], dest)
                            logging.info(f'    {C.GREEN}[Saved]{C.RESET} {dest}')
                        except requests.exceptions.RequestException as err:
                            logging.info(f'    {C.RED}x Failed to download \'{attachment["title"]}\': {err}{C.RESET}')
                    total += 1

        logging.info(f'\n  {C.GREEN}Total attachments found: {total}{C.RESET}')
                        
    def search_keywords_on_pages(self, keyword, space=None, download_dir=None):
        if space:
            pages = self.search_api_by_space(space, keyword)
        else:
            pages = self.search_api(keyword)

        if not isinstance(pages, dict):
            logging.info(pages)
            return

        if download_dir:
            os.makedirs(download_dir, exist_ok=True)
            logging.info(f"Downloading keyword matches to: {os.path.abspath(download_dir)}")

        self.grep_content_page(pages, keyword, download_dir=download_dir)
        

