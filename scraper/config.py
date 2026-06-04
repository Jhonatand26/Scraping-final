from pathlib import Path

BASE_OUTPUT_DIR = Path("output")

SITEMAP_INDEX_URL = "https://valledellili.org/sitemap_index.xml"

SITEMAP_TO_FOLDER = {
    "post-sitemap.xml": "posts",
    "post-sitemap2.xml": "posts",
    "page-sitemap.xml": "pages",
    "eventos-sitemap.xml": "eventos",
    "pda-sitemap.xml": "pda",
    "especialistas-sitemap.xml": "especialistas",
    "sedes-sitemap.xml": "sedes",
    "servicios-sitemap.xml": "servicios",
    "investigacion-sitemap.xml": "investigacion",
    "category-sitemap.xml": "categorias",
}

FOLDER_TO_SITEMAPS: dict[str, list[str]] = {}
for sitemap_file, folder in SITEMAP_TO_FOLDER.items():
    FOLDER_TO_SITEMAPS.setdefault(folder, []).append(sitemap_file)

MAX_WORKERS = 5
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
MAX_FILENAME_LENGTH = 200
