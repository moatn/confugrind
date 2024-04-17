# Confluance API Client

## Overview
This Python-based tool (`confugrind.py`) serves as a client for interacting with Atlassian Confluence through its REST API. It allows users to search for content, list spaces, fetch page details, and find attachments across Confluence pages based on specific criteria. Caus manual searching on the webapplication can be a grind to go trough. Especially large corperate environments.

## Features
- Search for keywords within all pages pages from all spaces, or just from a space.
- List all spaces in the Confluence instance.
- Fetch attachments from specified spaces with desired file extensions.
- Optional functionality to search for attachments related to specific keywords.

## Requirements
- Python 3.x
- `requests` library
- `json` and `argparse` modules
- `bs4` (BeautifulSoup) for HTML parsing
- `colorama` for colored terminal output
- `urllib3` for handling HTTP requests without SSL verification warnings

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/moatn/confugrind.git
   cd confugrind
   ```

2. **Install required Python libraries:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configuration:**
   - No additional configuration files are needed; all settings are passed as command-line arguments.

## Usage

```bash
python3 confugrind.py <baseurl> <token> [options]
```

### Command Line Arguments

- `baseurl`: Base URL of the Confluence instance.
- `token`: API token for authenticating with the Confluence instance.
- `--keyword`: Keyword to search within Confluence pages.
- `--space`: Space key to narrow down search or listing.
- `--ext`: Comma-separated list of file extensions to look for in attachments.
- `--sa`: Enable searching for attachments based on the specified `--ext`.
- `--search`: Enable search through Confluence using CQL queries.
- `--list-spaces`: List all available spaces in the Confluence instance.
- `--logfile`: Specify a filename for the logger, default will do something like `1713346155_170424_confluance.log`
- `--proxy`: Specify a proxy. Example: `--proxy http://127.0.0.1`.

### Examples

- **List all spaces:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-spaces
  ```

- **Search for a keyword across Confluence:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword password
  ```

- **Search for attachments in a specific space with certain file types:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --sa --space IT --ext pdf,docx,txt,kdb
  ```

## Limitations and improvements
- The current implementation does not handle all potential error scenarios
- Add hail mary option to search all spaces, all pages for certain attachments