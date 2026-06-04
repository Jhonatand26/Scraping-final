import argparse
import time

from scraper.config import FOLDER_TO_SITEMAPS
from scraper.sitemap import collect_all_entries
from scraper.fetcher import scrape_all


def main():
    parser = argparse.ArgumentParser(description="Web scraper for Fundación Valle del Lili sitemap")
    parser.add_argument(
        "--category",
        choices=list(FOLDER_TO_SITEMAPS.keys()),
        help="Scrape only a specific section",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Fundación Valle del Lili - Sitemap Scraper")
    print("=" * 60)
    print()

    print("[1/3] Collecting URLs from sitemaps...")
    entries = collect_all_entries(category=args.category)

    if not entries:
        print("No URLs found. Exiting.")
        return

    print(f"\n  Total URLs to process: {len(entries)}")
    folders = {}
    for e in entries:
        folders[e.folder] = folders.get(e.folder, 0) + 1
    for folder, count in sorted(folders.items()):
        print(f"    {folder}: {count}")

    print(f"\n[2/3] Scraping pages (5 workers, resume-enabled)...")
    start = time.time()
    results = scrape_all(entries)
    elapsed = time.time() - start

    print(f"\n[3/3] Done!")
    print("=" * 60)
    print(f"  Total:   {results['total']}")
    print(f"  Success: {results['success']} ({results['skipped']} skipped/resumed)")
    print(f"  Errors:  {results['errors']}")
    print(f"  Time:    {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print("=" * 60)

    if results["error_list"]:
        print(f"\nFailed URLs ({len(results['error_list'])}):")
        for err in results["error_list"][:20]:
            print(f"  {err}")
        if len(results["error_list"]) > 20:
            print(f"  ... and {len(results['error_list']) - 20} more")


if __name__ == "__main__":
    main()
