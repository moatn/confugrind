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
    
    def _as_keyword_list(self, keywords):
        #accept a single string or a list of keywords
        if isinstance(keywords, str):
            return [keywords]
        return list(keywords)

    def _build_text_cql(self, keywords):
        #OR semantics: a page matches if it contains any keyword
        return "(" + " OR ".join(f'text ~ "{k}"' for k in keywords) + ")"

    def _keyword_pattern(self, keywords):
        alternation = "|".join(re.escape(k) for k in keywords)
        return rf'^.*(?:{alternation}).*$'

    def search_api(self, keywords):
        keywords = self._as_keyword_list(keywords)
        try:
            response = self.r.get(
                f'{self.url}/rest/api/content/search',
                params={"cql": self._build_text_cql(keywords), "limit": 1000},
                headers=self.headers, proxies=self.proxy, verify=False)
            pages = self.create_dict_from_search(response.json())
            return pages

        except requests.exceptions.HTTPError as http_err:
            return f"HTTP Error occurred: {http_err}"
        except requests.exceptions.RequestException as err:
            return f"Error occurred: {err}"

    def search_api_by_space(self, space, keywords):
        keywords = self._as_keyword_list(keywords)
        try:
            response = self.r.get(
                f'{self.url}/rest/api/content/search',
                params={"cql": f"space = {space} and {self._build_text_cql(keywords)}", "limit": 1000},
                headers=self.headers, proxies=self.proxy, verify=False)
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
    
    def grep_content_page(self, data, keywords, download_dir=None):
        pattern = self._keyword_pattern(self._as_keyword_list(keywords))
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
        
    def _json_or_log(self, response, context):
        try:
            return response.json()
        except ValueError:
            snippet = response.text[:200].replace("\n", " ")
            logging.info(
                f"{C.RED}x {context}: non-JSON response "
                f"(HTTP {response.status_code}) {snippet!r}{C.RESET}")
            return None

    def list_page_versions(self, page_id):
        # Read the current version number from the page itself and iterate
        # 1..current. More portable than the /version child endpoint, which
        # is inconsistent across Confluence Server/DC/Cloud.
        try:
            response = self.r.get(
                f"{self.url}/rest/api/content/{page_id}?expand=version",
                headers={**self.headers, "Accept": "application/json"},
                proxies=self.proxy, verify=False)
            data = self._json_or_log(response, f"listing versions for {page_id}")
            if not data:
                return []
            current = data.get("version", {}).get("number")
            if not current:
                logging.info(f"{C.RED}x No version info for {page_id}{C.RESET}")
                return []
            return list(range(1, current + 1))
        except requests.exceptions.RequestException as err:
            logging.info(f"Error occurred while listing versions for {page_id}: {err}")
            return []

    def get_page_body_at_version(self, page_id, version, historical=True):
        try:
            status = "&status=historical" if historical else ""
            response = self.r.get(
                f"{self.url}/rest/api/content/{page_id}?version={version}{status}&expand=body.view",
                headers={**self.headers, "Accept": "application/json"},
                proxies=self.proxy, verify=False)
            data = self._json_or_log(response, f"fetching version {version} of {page_id}")
            if not data:
                return None
            return data["body"]["view"]["value"]
        except (requests.exceptions.RequestException, KeyError) as err:
            logging.info(f"Error occurred while fetching version {version} of {page_id}: {err}")
            return None

    def save_page_version(self, page_id, page_info, version, body, output_dir):
        title = page_info.get("title", page_id)
        page_folder = os.path.join(output_dir, f"{page_id}_{self.sanitize_filename(title)}")
        os.makedirs(page_folder, exist_ok=True)
        path = os.path.join(page_folder, f"v{version}.html")
        with open(path, "w", encoding="utf-8") as html_file:
            html_file.write(body)
        logging.info(f'    {C.GREEN}[Saved]{C.RESET} {path}')

    def list_attachment_versions(self, page_id):
        # For each attachment on a page return its title, current version
        # number and relative download path, so every version can be fetched.
        try:
            response = self.r.get(
                f"{self.url}/rest/api/content/{page_id}/child/attachment?expand=version&limit=1000",
                headers={**self.headers, "Accept": "application/json"},
                proxies=self.proxy, verify=False)
            data = self._json_or_log(response, f"listing attachments for {page_id}")
            if not data:
                return []
            attachments = []
            for attachment in data.get("results", []):
                attachments.append({
                    "title": attachment["title"],
                    "current_version": attachment.get("version", {}).get("number", 1),
                    "download": attachment["_links"]["download"],
                })
            return attachments
        except (requests.exceptions.RequestException, KeyError) as err:
            logging.info(f"Error occurred while listing attachments for {page_id}: {err}")
            return []

    def download_attachment_versions(self, page_id, page_info, output_dir,
                                     include=None, exclude=None, history=True):
        attachments = self.list_attachment_versions(page_id)
        if not attachments:
            return 0
        attachments = [a for a in attachments if self._matches_name_filter(a["title"], include, exclude)]
        if not attachments:
            return 0

        title = page_info.get("title", page_id)
        page_folder = os.path.join(output_dir, f"{page_id}_{self.sanitize_filename(title)}")
        attachments_folder = os.path.join(page_folder, "attachments")
        os.makedirs(attachments_folder, exist_ok=True)

        count = 0
        for attachment in attachments:
            name = attachment["title"]
            base, ext = os.path.splitext(name)
            #_links.download is a relative path with a query string; keep the
            # path and swap in the version we want.
            path_part = attachment["download"].split("?", 1)[0]
            current = attachment["current_version"]
            versions = range(1, current + 1) if history else [current]
            for version in versions:
                url = f"{self.url}{path_part}?version={version}"
                safe_name = self.sanitize_filename(f"{base}_v{version}{ext}")
                dest = self.unique_filepath(attachments_folder, safe_name)
                try:
                    self.download_attachment_file(url, dest)
                    logging.info(f'    {C.GREEN}[Saved]{C.RESET} {dest}')
                    count += 1
                except requests.exceptions.RequestException as err:
                    logging.info(f'    {C.RED}x Failed v{version} of \'{name}\': {err}{C.RESET}')
        return count

    def grep_page_history(self, page_id, page_info, keywords, download_dir=None):
        pattern = self._keyword_pattern(self._as_keyword_list(keywords))
        versions = self.list_page_versions(page_id)
        if not versions:
            return
        current = max(versions)
        title = page_info.get("title", page_id)
        webui = page_info.get("_links", {}).get("webui", "")
        attachments_downloaded = False
        for version in sorted(versions):
            body = self.get_page_body_at_version(page_id, version, historical=(version != current))
            if body is None:
                continue
            soup = BeautifulSoup(body, 'html.parser')
            pretty_html = soup.prettify()
            matches = re.findall(pattern, pretty_html, re.MULTILINE | re.IGNORECASE)
            if matches:
                tag = "current" if version == current else "history"
                for match in matches:
                    logging.info(f'{C.GREEN}[+] Match found in {tag}:{C.RESET}')
                    logging.info(f'{C.CYAN}[Page]{C.RESET} {title} {C.GREY}(v{version}){C.RESET}')
                    logging.info(f'{C.GREY}[URL]  {self.url}{webui}{C.RESET}')
                    logging.info(f'{C.YELLOW}[Hit]{C.RESET}  {match}')
                if download_dir:
                    self.save_page_version(page_id, page_info, version, body, download_dir)
                    #download every version of every attachment once per page
                    if not attachments_downloaded:
                        self.download_attachment_versions(page_id, page_info, download_dir)
                        attachments_downloaded = True

    def search_history(self, keywords, space=None, download_dir=None):
        keywords = self._as_keyword_list(keywords)
        if space:
            pages = self.list_pages_by_space(space)
        else:
            pages = {}
            spaces = self.list_spaces()
            if isinstance(spaces, dict):
                for space_id, space_details in spaces.items():
                    key = space_details.get("key")
                    if key:
                        space_pages = self.list_pages_by_space(key)
                        if isinstance(space_pages, dict):
                            pages.update(space_pages)

        if not isinstance(pages, dict) or not pages:
            logging.info(f'{C.RED}x No pages found to scan history{C.RESET}')
            return

        if download_dir:
            os.makedirs(download_dir, exist_ok=True)
            logging.info(f"Downloading history matches to: {os.path.abspath(download_dir)}")

        logging.info(f'\n{C.BOLD}Scanning page history ({len(pages)} pages) for keywords: {", ".join(keywords)}{C.RESET}')
        for page_id, page_info in pages.items():
            self.grep_page_history(page_id, page_info, keywords, download_dir=download_dir)

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

    def list_urls_by_space(self, space):
        logging.info(f'\n{C.BOLD}Listing all page URLs in space: {space}{C.RESET}')
        pages = self.list_pages_by_space(space)
        if not pages:
            logging.info(f'  {C.RED}x No pages found in space \'{space}\'{C.RESET}')
            return

        for page_id, page_info in pages.items():
            logging.info(f'  {C.CYAN}{page_info["title"]}{C.RESET}')
            logging.info(f'  {C.GREY}{self.url + page_info["_links"]["webui"]}{C.RESET}')

        logging.info(f'\n  {C.GREEN}Total pages: {len(pages)}{C.RESET}')

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

    def list_all_attachments_in_space(self, space, include=None, exclude=None, output_dir=None, history=True):
        logging.info(f'\n{C.BOLD}Listing all attachments in space: {space}{C.RESET}')
        if include:
            logging.info(f'  {C.GREY}include: {", ".join(include)}{C.RESET}')
        if exclude:
            logging.info(f'  {C.GREY}exclude: {", ".join(exclude)}{C.RESET}')
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            logging.info(f'  {C.GREY}output:  {os.path.abspath(output_dir)}{C.RESET}')
            logging.info(f'  {C.GREY}history: {"all versions" if history else "current only"}{C.RESET}')

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

                for attachment in filtered:
                    logging.info(f'    {C.YELLOW}[Attachment]{C.RESET} {attachment["title"]}')
                    logging.info(f'    {C.GREY}{attachment["url"]}{C.RESET}')
                    total += 1

                if output_dir:
                    self.download_attachment_versions(
                        page_id, page_info, output_dir,
                        include=include, exclude=exclude, history=history)

        logging.info(f'\n  {C.GREEN}Total attachments found: {total}{C.RESET}')
                        
    def search_keywords_on_pages(self, keywords, space=None, download_dir=None):
        keywords = self._as_keyword_list(keywords)
        if space:
            pages = self.search_api_by_space(space, keywords)
        else:
            pages = self.search_api(keywords)

        if not isinstance(pages, dict):
            logging.info(pages)
            return

        if download_dir:
            os.makedirs(download_dir, exist_ok=True)
            logging.info(f"Downloading keyword matches to: {os.path.abspath(download_dir)}")

        self.grep_content_page(pages, keywords, download_dir=download_dir)
        

