from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
import re

import requests
from bs4 import BeautifulSoup

ARCHIVE_DOWNLOAD_PREFIX = "https://archive.org/download/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class FileItem:
    name: str
    url: str
    size_label: str


def parse_item_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Item ID or URL is required.")
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("Invalid Internet Archive URL.")
        if parts[0] in {"details", "download"} and len(parts) >= 2:
            return parts[1]
        return parts[-1]
    return value


def build_download_url(item_id: str) -> str:
    return f"{ARCHIVE_DOWNLOAD_PREFIX}{item_id}"


def fetch_directory_listing(download_url: str, timeout: int = 20) -> str:
    response = requests.get(download_url, timeout=timeout, headers=DEFAULT_HEADERS)
    response.raise_for_status()
    return response.text


def parse_directory_listing(html: str, base_url: str | None = None) -> tuple[str, list[FileItem]]:
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_title(soup)
    table = soup.find("table", class_="directory-listing-table")
    if table is None:
        raise ValueError("Directory listing table not found.")
    rows = table.find_all("tr")
    files: list[FileItem] = []
    for row in rows:
        link = row.find("a")
        if link is None:
            continue
        name = link.get_text(strip=True)
        href = link.get("href")
        if not href or "Go to parent directory" in name:
            continue
        if base_url:
            href = urljoin(base_url.rstrip("/") + "/", href)
        size_cell = row.find_all("td")
        size_label = ""
        if len(size_cell) >= 3:
            size_label = size_cell[2].get_text(strip=True)
        files.append(FileItem(name=name, url=href, size_label=size_label))
    if not files:
        raise ValueError("No downloadable files found.")
    return title, files


def sanitize_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", name).strip()
    return cleaned or "internet_archive_download"


def format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _extract_title(soup: BeautifulSoup) -> str:
    header = soup.find("h1")
    if header:
        text = header.get_text(strip=True)
        if text.lower().startswith("files for "):
            return text[9:].strip()
        return text
    title = soup.find("title")
    if title:
        text = title.get_text(strip=True)
        suffix = " directory listing"
        if text.endswith(suffix):
            return text[: -len(suffix)].strip()
        return text
    return "internet_archive_download"
