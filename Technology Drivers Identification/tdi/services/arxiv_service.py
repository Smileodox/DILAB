import asyncio
import httpx
import xml.etree.ElementTree as ET
from tdi.config import get_settings
from tdi.models.schemas import ArxivPaper

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivService:
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self):
        self.settings = get_settings()

    def _build_query(self, technology: str) -> str:
        terms = technology.replace("-", " ").split()
        search = " AND ".join(f'all:"{term}"' for term in terms[:4])
        return f"({search}) AND (cat:cs.NI OR cat:eess.SP OR cat:cs.IT OR cat:cs.AI)"

    def _parse_entry(self, entry: ET.Element, technology: str) -> ArxivPaper | None:
        id_elem = entry.find("atom:id", ATOM_NS)
        title_elem = entry.find("atom:title", ATOM_NS)
        summary_elem = entry.find("atom:summary", ATOM_NS)
        published_elem = entry.find("atom:published", ATOM_NS)

        if id_elem is None or title_elem is None or summary_elem is None:
            return None

        arxiv_id = id_elem.text.split("/abs/")[-1]
        authors = [
            a.find("atom:name", ATOM_NS).text
            for a in entry.findall("atom:author", ATOM_NS)
            if a.find("atom:name", ATOM_NS) is not None
        ]
        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", ATOM_NS)
        ]

        title = title_elem.text or ""
        summary = summary_elem.text or ""

        return ArxivPaper(
            arxiv_id=arxiv_id,
            title=" ".join(title.split()),
            authors=authors,
            abstract=" ".join(summary.split()),
            published=published_elem.text[:10] if published_elem is not None else "",
            categories=categories,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            technology=technology,
        )

    async def fetch_paper_for_technology(self, technology: str) -> ArxivPaper | None:
        params = {
            "search_query": self._build_query(technology),
            "start": 0,
            "max_results": self.settings.arxiv_max_results_per_tech,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()

        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", ATOM_NS)

        if not entries:
            params["search_query"] = f'all:"{technology}"'
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
            root = ET.fromstring(response.text)
            entries = root.findall("atom:entry", ATOM_NS)

        if entries:
            return self._parse_entry(entries[0], technology)
        return None

    async def fetch_papers_for_technologies(
        self, technologies: list[str]
    ) -> list[ArxivPaper]:
        unique = list(dict.fromkeys(technologies))
        tasks = [self.fetch_paper_for_technology(tech) for tech in unique]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        papers = []
        for tech, result in zip(unique, results):
            if isinstance(result, ArxivPaper):
                papers.append(result)
            elif isinstance(result, Exception):
                print(f"arXiv fetch failed for '{tech}': {result}")
        return papers
