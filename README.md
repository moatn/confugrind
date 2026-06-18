# Confluance API Client

## Overview
This Python-based tool (`confugrind.py`) serves as a client for interacting with Atlassian Confluence through its REST API. It allows users to search for content, list spaces, fetch page details, and find attachments across Confluence pages based on specific criteria. Caus manual searching on the webapplication can be a grind to go trough. Especially large corperate environments.

## Features
- Search for keywords within all pages from all spaces, or just from a space.
- Scans the full version history of pages by default, catching secrets that were removed from the current version (disable with `--no-history`).
- List all spaces in the Confluence instance.
- List all page URLs in a space.
- Fetch attachments from specified spaces with desired file extensions.
- List all attachments in a space with optional filename include/exclude filters.
- Download all keyword-matching pages and their attachments to disk.
- Download space attachments to disk with glob-based filename filtering.

## Requirements
- Python 3.x
- `requests` library
- `json` and `argparse` modules
- `bs4` (BeautifulSoup) for HTML parsing
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
- `--search`: Enable search through Confluence. By default this also scans the full version history of every page in scope (not just the current version), so it catches secrets that were edited out of the live page. Optionally scoped with `--space` and saved with `--download`. Note: history scanning enumerates every page and version in scope, so it is slower than a current-only search.
- `--no-history`: Restrict `--search` to the current version of pages only (the original, faster CQL-based behaviour).
- `--list-spaces`: List all available spaces in the Confluence instance.
- `--list-space-urls`: List all page titles and URLs in a given space.
- `--list-space-attachments`: List all attachments in a given space (no extension filter required).
- `--include-name`: Only show attachments whose filename matches any of these glob patterns (e.g. `*.pdf,password*`).
- `--exclude-name`: Skip attachments whose filename matches any of these glob patterns (e.g. `*.png,*.jpg`).
- `--output`: Download attachments from `--list-space-attachments` to this directory.
- `--download`: Download keyword-matching pages and all attachments to the provided local directory (requires `--search` and `--keyword`).
- `--logfile`: Specify a filename for the logger, default will do something like `1713346155_170424_confluance.log`
- `--proxy`: Specify a proxy. Example: `--proxy http://127.0.0.1:8080`.

### Examples

- **List all spaces:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-spaces
  ```

- **List all page URLs in a space:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-space-urls IT
  ```

- **Search for a keyword across Confluence (includes full page history by default):**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword password
  ```

- **Search the current version only (faster, no history):**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword password --no-history
  ```

- **History search scoped to a space, saving matching versions to disk:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword password --space IT --download ./loot
  ```

- **Search for attachments in a specific space with certain file types:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --sa --space IT --ext pdf,docx,txt,kdb
  ```

- **Download all pages (and their attachments) that match a keyword:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --search --keyword password --download ./loot
  ```

- **List all attachments in a space:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-space-attachments IT
  ```

- **List and download only PDFs and Word docs, skip images:**
  ```bash
  python3 confugrind.py https://some-confluence.internal VrS7zg5Et9FJ3AdxR2y3mD6BbNc1XaGpMhVfC8yQwIu9TlEx --list-space-attachments IT --include-name '*.pdf,*.docx' --exclude-name '*.png,*.jpg' --output ./loot
  ```

### Download Output Structure

When `--download` or `--output` is used, each page is stored in a dedicated folder named `<page_id>_<page_title>`.

```text
./loot/
  <page_id>_<page_title>/
    page.html
    attachments/
      <attachment files>
```

When history scanning is active (the default for `--search`) and `--download` is used, each matching page version is saved as `v<version>.html`, and **every version of every attachment** on that page is downloaded as `<name>_v<version>.<ext>`:

```text
./loot/
  <page_id>_<page_title>/
    v3.html
    v7.html
    attachments/
      config_v1.xml
      config_v2.xml
      backup_v1.kdbx
```

This catches attachment versions that were later replaced or removed from the live page (e.g. a secret-laden config that was swapped for a sanitized one).

## Limitations
- The current implementation does not handle all potential error scenarios
