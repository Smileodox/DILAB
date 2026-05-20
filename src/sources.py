import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "DiLab-Foresight-Research/1.0 (LMU Munich; academic research)"}
TIMEOUT = 15


def _is_clean_html(text: str) -> bool:
    latex_noise = sum(1 for m in re.finditer(r"\\[a-zA-Z]{2,}", text[:2000]))
    return latex_noise < 10 and len(text) > 500


def fetch_arxiv(arxiv_id: str) -> str:
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id.strip())

    for suffix in ["v1", "v2", ""]:
        try:
            url = f"https://arxiv.org/html/{arxiv_id}{suffix}"
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "math", "mjx-container"]):
                tag.decompose()
            article = soup.find("article") or soup.find("main") or soup.find("body")
            if not article:
                continue
            text = article.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            if _is_clean_html(text):
                return text[:15000]
        except (requests.RequestException, Exception):
            continue

    try:
        resp = requests.get(f"https://arxiv.org/abs/{arxiv_id}", headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            parts = []
            title_el = soup.find("h1", class_="title")
            if title_el:
                parts.append(title_el.get_text(strip=True).replace("Title:", "").strip())
            abstract_el = soup.find("blockquote", class_="abstract")
            if abstract_el:
                parts.append(abstract_el.get_text(strip=True).replace("Abstract:", "").strip())
            if parts:
                return "\n\n".join(parts)
    except (requests.RequestException, Exception):
        pass

    return ""


def fetch_webpage(url: str, selectors: list[str] | None = None) -> str:
    if not url or len(url) < 10:
        return ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        if selectors:
            parts = []
            for sel in selectors:
                for el in soup.select(sel):
                    parts.append(el.get_text(separator="\n", strip=True))
            text = "\n\n".join(parts)
            if len(text) > 200:
                return text[:15000]

        for container_tag in ["article", "main", "[role='main']"]:
            container = soup.select_one(container_tag) if "[" in container_tag else soup.find(container_tag)
            if container:
                text = container.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return re.sub(r"\n{3,}", "\n\n", text)[:15000]

        paragraphs = soup.find_all(["p", "li", "h1", "h2", "h3", "h4"])
        text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        return re.sub(r"\n{3,}", "\n\n", text)[:15000] if len(text) > 200 else ""

    except (requests.RequestException, Exception):
        return ""


def extract_arxiv_id(url: str) -> str | None:
    m = re.search(r"arxiv\.org/(?:abs|html|pdf)/(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else None
