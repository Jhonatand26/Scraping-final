"""Content extraction and Markdown conversion for Valle del Lili pages.

Strategy:
  1. Parse raw HTML with BeautifulSoup.
  2. Extract metadata (title, date, categories) BEFORE cleaning.
  3. Remove noise elements (modals, menus, scripts, hidden elements).
  4. Extract links AFTER cleaning so nav/footer links are excluded.
  5. Find best content container — preferring ``div.content-block``
     (the pattern used site-wide), falling back to full ``<body>``.
  6. Convert cleaned HTML to Markdown, preserving ALL links.
  7. For specialist pages, run a dedicated structured extractor that
     captures: specialty, extension, sedes, education, languages, keywords.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as md

# ---------------------------------------------------------------------------
# Noise removal
# ---------------------------------------------------------------------------

REMOVE_TAGS = [
    "script", "style", "noscript", "iframe", "svg",
]

REMOVE_SELECTORS: list[tuple[str | None, dict]] = [
    ("header", {}),
    ("footer", {}),
    ("nav", {}),
    ("div", {"class_": lambda c: c and "wrapper-modal" in c}),
    ("div", {"class_": lambda c: c and "backdrop-overlay" in c}),
    (None, {"class_": lambda c: c and "print:hidden" in c}),
    (None, {"class_": lambda c: c and "cookie" in c}),
    (None, {"class_": lambda c: c and "popup" in c}),
    (None, {"class_": lambda c: c and "modal" in c}),
]

# Link patterns to EXCLUDE from the "Enlaces" section
_JUNK_LINK_PATTERNS = re.compile(
    r"sharer/sharer|intent/tweet|dialog/send|sharing/share-offsite"
    r"|api\.whatsapp\.com/send\?text="
    r"|zonapagos\.net"
    r"|googletagmanager"
    r"|facebook\.com/fundacion"
    r"|instagram\.com/fundacion"
    r"|linkedin\.com/company"
    r"|spotify\.com/show"
    r"|x\.com/fvl"
    r"|youtube\.com/user"
    r"|forms\.cloud\.microsoft",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

BASE_URL = "https://valledellili.org"


def extract_content(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    # --- metadata: extract BEFORE cleanup ---
    title = _extract_title(soup)
    date = _extract_date(soup)
    categories = _extract_categories(soup)

    if "/directorio-medico/" in url:
        profile = _extract_specialist_profile(soup, url)
        _clean_soup(soup)
        content_links = _extract_content_links(soup, url)
        body_md = _build_specialist_markdown(profile)
    else:
        _clean_soup(soup)
        content_links = _extract_content_links(soup, url)
        body_html = _extract_body(soup)
        body_md = _html_to_markdown(body_html)

    return {
        "title": title,
        "date": date,
        "categories": categories,
        "body": body_md,
        "links": content_links,
    }


# ---------------------------------------------------------------------------
# Metadata extraction (run BEFORE cleanup)
# ---------------------------------------------------------------------------

def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        return text.split("|")[0].split("–")[0].split("-")[0].strip()

    return "Sin título"


def _extract_date(soup: BeautifulSoup) -> str | None:
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return time_tag["datetime"]

    for cls in ["post-date", "date", "entry-date", "published"]:
        elem = soup.find(class_=cls)
        if elem:
            text = elem.get_text(strip=True)
            if text:
                return text

    date_pattern = re.compile(
        r"\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|octubre|noviembre|diciembre)\s+\d{4}",
        re.IGNORECASE,
    )
    body = soup.find("body")
    if body:
        text = body.get_text()[:5000]
        match = date_pattern.search(text)
        if match:
            return match.group(0)

    return None


def _extract_categories(soup: BeautifulSoup) -> list[str]:
    cats: list[str] = []

    container = soup.find(class_="post-categories")
    if container:
        for a in container.find_all("a"):
            text = a.get_text(strip=True)
            if text:
                cats.append(text)

    if not cats:
        for a in soup.find_all("a", rel="tag"):
            text = a.get_text(strip=True)
            if text:
                cats.append(text)

    if not cats:
        for a in soup.find_all("a", class_=lambda c: c and "btn-pill" in c):
            text = a.get_text(strip=True)
            if text and text not in cats:
                cats.append(text)

    return cats


# ---------------------------------------------------------------------------
# Link extraction — runs AFTER cleanup to exclude nav/footer/social
# ---------------------------------------------------------------------------

def _extract_content_links(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Extract only meaningful content links (post-cleanup)."""
    links: list[dict] = []
    seen: set[str] = set()

    page_domain = urlparse(page_url).netloc

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        full_url = urljoin(page_url, href)

        # Skip junk links (social sharing, payment gateways, etc.)
        if _JUNK_LINK_PATTERNS.search(full_url):
            continue

        # Skip tel: and mailto: for the links section (kept in body)
        parsed = urlparse(full_url)
        if parsed.scheme in ("tel", "mailto"):
            continue

        # Skip self-links
        if full_url.rstrip("/") == page_url.rstrip("/"):
            continue

        text = a.get_text(strip=True)
        if not text:
            continue

        if full_url not in seen:
            seen.add(full_url)
            links.append({"text": text, "url": full_url})

    return links


# ---------------------------------------------------------------------------
# Noise cleanup
# ---------------------------------------------------------------------------

def _clean_soup(soup: BeautifulSoup):
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for tag_name, kwargs in REMOVE_SELECTORS:
        for tag in soup.find_all(tag_name, **kwargs):
            tag.decompose()

    for tag in soup.find_all("form"):
        tag.decompose()

    for tag in soup.find_all("button"):
        tag.decompose()


# ---------------------------------------------------------------------------
# Body extraction — generic pages
# ---------------------------------------------------------------------------

def _extract_body(soup: BeautifulSoup) -> str:
    body = soup.find("body")
    if not body:
        return ""

    # Strategy 1: find div.content-block with the most content
    content_blocks = body.find_all(
        "div", class_=lambda c: c and "content-block" in c
    )
    if content_blocks:
        best = max(content_blocks, key=lambda b: len(b.get_text(strip=True)))
        if len(best.get_text(strip=True)) > 50:
            return str(best)

    # Strategy 2: meaningful <section> elements
    sections = body.find_all("section")
    if sections:
        meaningful = [
            s for s in sections
            if len(s.get_text(strip=True)) > 30
        ]
        if meaningful:
            return "\n".join(str(s) for s in meaningful)

    # Strategy 3: classic selectors
    for selector_fn in [
        lambda b: b.find("article"),
        lambda b: b.find("main"),
        lambda b: b.find(class_="content"),
        lambda b: b.find(id="content"),
    ]:
        elem = selector_fn(body)
        if elem and len(elem.get_text(strip=True)) > 50:
            return str(elem)

    # Fallback: entire body
    return str(body)


# ---------------------------------------------------------------------------
# Specialist‑specific extraction
# ---------------------------------------------------------------------------

_LEGAL_JUNK = re.compile(
    r"Ley\s+1581|Decreto\s+1074|datos\s+personales|Responsable\s+del\s+Tratamiento",
    re.IGNORECASE,
)


def _find_profile_content_block(soup: BeautifulSoup) -> tuple[Tag | None, Tag | None]:
    """Find the content-block that has the specialist profile (contains aside+h1).

    Returns (detail_panel, aside) or (None, None).
    """
    for cb in soup.find_all(
        "div", class_=lambda c: c and "content-block" in c
    ):
        aside = cb.find("aside")
        if aside and cb.find("h1"):
            detail = aside.find_next_sibling("div")
            return detail, aside
    return None, None


def _find_shadow_block(container: Tag, heading_keyword: str) -> Tag | None:
    """Find a div.shadow-xs whose h4 contains the given keyword."""
    if container is None:
        return None
    for div in container.find_all(
        "div", class_=lambda c: c and "shadow-xs" in c
    ):
        h4 = div.find("h4")
        if h4 and heading_keyword in h4.get_text().lower():
            return div
    return None


def _extract_specialist_profile(soup: BeautifulSoup, url: str) -> dict:
    profile: dict = {
        "nombre": "",
        "especialidad": "",
        "foto_url": "",
        "extension": "",
        "telefono": "",
        "sedes": [],
        "formacion": [],
        "idiomas": [],
        "keywords": [],
        "cita_url": "",
    }

    detail_panel, aside = _find_profile_content_block(soup)

    # --- Name + Specialty (in aside sidebar) ---
    h1 = soup.find("h1")
    if h1:
        profile["nombre"] = h1.get_text(strip=True)

        specialty_p = h1.find_next_sibling("p")
        if not specialty_p:
            parent = h1.parent
            if parent:
                specialty_p = parent.find("p")
        if specialty_p:
            text = specialty_p.get_text(strip=True)
            if text and not _LEGAL_JUNK.search(text):
                profile["especialidad"] = text

    # --- Photo ---
    img = soup.find("img", src=lambda s: s and "fotos-medicos" in s)
    if img:
        profile["foto_url"] = urljoin(url, img.get("src", ""))

    # --- Phone & Extension ---
    for a in soup.find_all("a", href=lambda h: h and h.startswith("tel:")):
        text = a.get_text(strip=True)
        href = a["href"]
        if "," in href:
            profile["extension"] = text
        else:
            profile["telefono"] = text

    # --- Sedes (in aside sidebar) ---
    search_area = aside or soup
    sedes_label = search_area.find(
        "p",
        string=lambda t: t and "Sede" in t,
        class_=lambda c: c and "font-primary-600" in c,
    )
    if sedes_label:
        container = sedes_label.find_parent("div")
        if container:
            for li in container.find_all("li"):
                sede = li.get_text(strip=True)
                if sede:
                    profile["sedes"].append(sede)

    # --- Keywords (detail panel → div.shadow-xs with h4 "Palabras clave") ---
    kw_block = _find_shadow_block(detail_panel, "clave")
    if kw_block:
        for a in kw_block.find_all("a"):
            text = a.get_text(strip=True)
            if text:
                profile["keywords"].append(text)

    # --- Education (detail panel → div.shadow-xs with h4 "Formación") ---
    edu_block = _find_shadow_block(detail_panel, "formaci")
    if edu_block:
        for article_tag in edu_block.find_all("article"):
            ps = article_tag.find_all("p")
            if len(ps) >= 2:
                degree = ps[0].get_text(strip=True)
                university = ps[1].get_text(strip=True)
                combined = f"{degree} {university}"
                if _LEGAL_JUNK.search(combined):
                    continue
                if degree or university:
                    entry = f"{degree} — {university}" if university else degree
                    profile["formacion"].append(entry)
            elif len(ps) == 1:
                text = ps[0].get_text(strip=True)
                if text and not _LEGAL_JUNK.search(text):
                    profile["formacion"].append(text)

    # --- Languages (detail panel → div.shadow-xs with h4 "idiomas") ---
    lang_block = _find_shadow_block(detail_panel, "idioma")
    if lang_block:
        for span in lang_block.find_all("span"):
            text = span.get_text(strip=True)
            if text and len(text) < 50:
                profile["idiomas"].append(text)

    # --- Appointment link ---
    cita_link = soup.find("a", href=lambda h: h and "solicitar-cita" in h)
    if cita_link:
        profile["cita_url"] = urljoin(url, cita_link["href"])

    return profile


def _build_specialist_markdown(profile: dict) -> str:
    lines: list[str] = []

    if profile["foto_url"]:
        lines.append(f"![Foto del especialista]({profile['foto_url']})")
        lines.append("")

    if profile["especialidad"]:
        lines.append(f"**Especialidad:** {profile['especialidad']}")
        lines.append("")

    if profile["extension"] or profile["telefono"]:
        phone = profile["telefono"] or "(+57) 602 331 9090"
        lines.append(f"**Teléfono:** {phone}")
        if profile["extension"]:
            lines.append(f"**Extensión:** {profile['extension']}")
        lines.append("")

    if profile["sedes"]:
        lines.append("**Sedes:**")
        for sede in profile["sedes"]:
            lines.append(f"- {sede}")
        lines.append("")

    if profile["formacion"]:
        lines.append("## Formación académica")
        lines.append("")
        for item in profile["formacion"]:
            lines.append(f"- {item}")
        lines.append("")

    if profile["idiomas"]:
        lines.append("**Idiomas:** " + ", ".join(profile["idiomas"]))
        lines.append("")

    if profile["keywords"]:
        lines.append("## Palabras clave")
        lines.append("")
        lines.append(", ".join(profile["keywords"]))
        lines.append("")

    if profile["cita_url"]:
        lines.append(f"[Agendar cita]({profile['cita_url']})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML → Markdown conversion
# ---------------------------------------------------------------------------

def _html_to_markdown(html: str) -> str:
    if not html:
        return ""

    text = md(
        html,
        heading_style="ATX",
        bullets="-",
        convert=["a", "p", "h1", "h2", "h3", "h4", "h5", "h6",
                 "ul", "ol", "li", "strong", "em", "b", "i",
                 "blockquote", "pre", "code", "table", "thead",
                 "tbody", "tr", "th", "td", "br", "hr", "dl", "dt", "dd",
                 "img"],
    )

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)
    text = text.strip()

    return text


# ---------------------------------------------------------------------------
# Final Markdown file formatting
# ---------------------------------------------------------------------------

def format_markdown_file(entry_url: str, section: str, data: dict) -> str:
    lines = ["---"]
    lines.append(f'title: "{_escape_yaml(data["title"])}"')
    lines.append(f'url: "{entry_url}"')
    if data.get("date"):
        lines.append(f'fecha: "{data["date"]}"')
    if data.get("categories"):
        lines.append("categorias:")
        for cat in data["categories"]:
            lines.append(f'  - "{_escape_yaml(cat)}"')
    lines.append(f"seccion: {section}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {data['title']}")
    lines.append("")
    lines.append(data["body"])
    lines.append("")

    links = data.get("links", [])
    if links:
        lines.append("---")
        lines.append("")
        lines.append("## Enlaces encontrados en esta página")
        lines.append("")
        for link in links:
            display = link["text"][:120]
            lines.append(f"- [{display}]({link['url']})")
        lines.append("")

    return "\n".join(lines)


def _escape_yaml(text: str) -> str:
    return text.replace('"', '\\"').replace("\n", " ")
