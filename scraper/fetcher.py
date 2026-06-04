from __future__ import annotations

import re
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scrapling import Fetcher

from .config import (
    BASE_OUTPUT_DIR,
    MAX_FILENAME_LENGTH,
    MAX_RETRIES,
    MAX_WORKERS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
)
from .extractor import extract_content, format_markdown_file
from .sitemap import SitemapEntry

logging.getLogger("scrapling").setLevel(logging.ERROR)

_rate_lock = threading.Lock()
_last_request_time: dict[int, float] = {}


def _sanitize_filename(slug: str) -> str:
    slug = re.sub(r'[<>:"/\\|?*]', "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) > MAX_FILENAME_LENGTH:
        slug = slug[:MAX_FILENAME_LENGTH]
    return slug or "page"


def _output_path(entry: SitemapEntry) -> Path:
    filename = _sanitize_filename(entry.slug) + ".md"
    return BASE_OUTPUT_DIR / entry.folder / filename


def _rate_limit():
    tid = threading.get_ident()
    with _rate_lock:
        last = _last_request_time.get(tid, 0)
        elapsed = time.time() - last
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        _last_request_time[tid] = time.time()


def _scrape_one(entry: SitemapEntry, index: int, total: int) -> tuple[bool, str]:
    out_path = _output_path(entry)
    if out_path.exists():
        return True, f"[{index}/{total}] Skipped (exists): {entry.slug}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            _rate_limit()
            fetcher = Fetcher(timeout=REQUEST_TIMEOUT)
            page = fetcher.get(entry.url)

            if page.status != 200:
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                return False, f"[{index}/{total}] HTTP {page.status}: {entry.slug}"

            html = page.html_content
            data = extract_content(html, entry.url)
            markdown = format_markdown_file(entry.url, entry.folder, data)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(markdown, encoding="utf-8")

            return True, f"[{index}/{total}] OK: {entry.slug}"

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            return False, f"[{index}/{total}] Error ({type(e).__name__}): {entry.slug}"

    return False, f"[{index}/{total}] Failed after retries: {entry.slug}"


def scrape_all(entries: list[SitemapEntry]) -> dict:
    total = len(entries)
    success = 0
    skipped = 0
    errors = 0
    error_list: list[str] = []

    for folder in {e.folder for e in entries}:
        (BASE_OUTPUT_DIR / folder).mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_scrape_one, entry, i + 1, total): entry
            for i, entry in enumerate(entries)
        }

        for future in as_completed(futures):
            ok, msg = future.result()
            print(msg)
            if "Skipped" in msg:
                skipped += 1
                success += 1
            elif ok:
                success += 1
            else:
                errors += 1
                error_list.append(msg)

    return {
        "total": total,
        "success": success,
        "skipped": skipped,
        "errors": errors,
        "error_list": error_list,
    }
