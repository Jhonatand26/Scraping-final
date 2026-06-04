from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

from lxml import etree
from scrapling import Fetcher

from .config import SITEMAP_INDEX_URL, SITEMAP_TO_FOLDER

logging.getLogger("scrapling").setLevel(logging.ERROR)

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class SitemapEntry:
    url: str
    lastmod: str | None
    folder: str
    slug: str


def _fetch_xml(url: str) -> bytes:
    page = Fetcher().get(url)
    return page.html_content.encode("utf-8") if isinstance(page.html_content, str) else page.html_content


def _extract_sitemap_key(url: str) -> str:
    return urlparse(url).path.strip("/").split("/")[-1]


def parse_sitemap_index(index_url: str = SITEMAP_INDEX_URL) -> list[str]:
    raw = _fetch_xml(index_url)
    tree = etree.fromstring(raw)
    return [loc.text for loc in tree.findall(".//sm:loc", NS) if loc.text]


def parse_child_sitemap(sitemap_url: str) -> list[SitemapEntry]:
    key = _extract_sitemap_key(sitemap_url)
    folder = SITEMAP_TO_FOLDER.get(key)
    if folder is None:
        return []

    raw = _fetch_xml(sitemap_url)
    tree = etree.fromstring(raw)

    entries = []
    for url_elem in tree.findall(".//sm:url", NS):
        loc = url_elem.find("sm:loc", NS)
        lastmod = url_elem.find("sm:lastmod", NS)
        if loc is None or not loc.text:
            continue

        page_url = loc.text.strip()
        slug = _url_to_slug(page_url)
        if not slug:
            continue

        entries.append(SitemapEntry(
            url=page_url,
            lastmod=lastmod.text.strip() if lastmod is not None and lastmod.text else None,
            folder=folder,
            slug=slug,
        ))

    return entries


def _url_to_slug(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "index"
    parts = path.split("/")
    return parts[-1] if parts[-1] else (parts[-2] if len(parts) > 1 else "index")


def collect_all_entries(category: str | None = None) -> list[SitemapEntry]:
    sitemap_urls = parse_sitemap_index()
    all_entries: list[SitemapEntry] = []

    for sitemap_url in sitemap_urls:
        key = _extract_sitemap_key(sitemap_url)
        folder = SITEMAP_TO_FOLDER.get(key)
        if folder is None:
            continue
        if category and folder != category:
            continue

        print(f"  Parsing sitemap: {key} -> {folder}/")
        entries = parse_child_sitemap(sitemap_url)
        all_entries.extend(entries)
        print(f"    Found {len(entries)} URLs")

    return all_entries
