import re
from collections import Counter
from tdi.models.schemas import ArxivPaper, ExtractedEntity

SPECTRUM_BANDS = [
    "sub-6 GHz", "mmWave", "24 GHz", "28 GHz", "39 GHz", "60 GHz",
    "THz", "C-band", "Ka-band", "Ku-band", "L-band", "S-band",
    "700 MHz", "3.5 GHz", "26 GHz", "47 GHz",
]

STANDARDS = [
    "3GPP", "IEEE 802.11", "IEEE 802.15", "ITU-R", "ETSI", "O-RAN",
    "5G NR", "6G", "Wi-Fi 7", "Release 18", "Release 19", "DVB",
]

REGULATORY_AGENCIES = [
    "FCC", "Ofcom", "BNetzA", "CEPT", "ITU", "EC", "BEREC",
    "WRC", "GSMA", "3GPP", "ETSI",
]

TECHNOLOGY_KEYWORDS = [
    "MIMO", "beamforming", "massive MIMO", "OFDM", "O-RAN", "Open RAN",
    "cognitive radio", "spectrum sensing", "dynamic spectrum sharing",
    "full duplex", "cell-free", "RIS", "reconfigurable intelligent surface",
    "NTN", "non-terrestrial network", "satellite", "LEO", "HAPS",
    "edge computing", "network slicing", "digital twin", "AI-native",
    "machine learning", "deep learning", "federated learning",
    "quantum communication", "optical wireless", "LiFi", "V2X",
    "URLLC", "eMBB", "mMTC", "ISAC", "integrated sensing",
]

POLICY_TERMS = [
    "spectrum auction", "spectrum licensing", "unlicensed spectrum",
    "shared spectrum", "spectrum refarming", "interference management",
    "harmonization", "white space", "spectrum cap", "net neutrality",
    "regulatory sandbox", "spectrum trading", "geolocation database",
]

INDUSTRY_KEYWORDS = [
    "telecommunications", "defense", "aerospace", "automotive", "healthcare",
    "finance", "energy", "agriculture", "manufacturing", "media", "education",
    "government", "maritime", "retail", "logistics", "smart cities", "IoT",
    "satellite", "broadcasting", "transportation", "mining", "utilities",
    "entertainment", "agritech", "fintech", "insurance", "construction",
    "public safety", "rail", "aviation", "semiconductor", "cloud computing",
]


class NLPService:
    def clean_text(self, text: str | None) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s\-\.,;:()/%]", "", text)
        return text.strip()

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks if chunks else [text]

    def extract_entities(self, papers: list[ArxivPaper]) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        full_text = " ".join(p.abstract + " " + p.title for p in papers).lower()

        for band in SPECTRUM_BANDS:
            if band.lower() in full_text:
                entities.append(ExtractedEntity(entity_type="spectrum_band", value=band, confidence=0.85))

        for std in STANDARDS:
            if std.lower() in full_text:
                entities.append(ExtractedEntity(entity_type="standard", value=std, confidence=0.80))

        for agency in REGULATORY_AGENCIES:
            if agency.lower() in full_text:
                entities.append(ExtractedEntity(entity_type="regulatory_agency", value=agency, confidence=0.75))

        for tech in TECHNOLOGY_KEYWORDS:
            if tech.lower() in full_text:
                entities.append(ExtractedEntity(entity_type="technology", value=tech, confidence=0.70))

        for policy in POLICY_TERMS:
            if policy.lower() in full_text:
                entities.append(ExtractedEntity(entity_type="policy", value=policy, confidence=0.72))

        tech_names = set()
        for paper in papers:
            tech_names.add(paper.technology)
            for word in paper.title.split():
                if len(word) > 4 and word[0].isupper():
                    tech_names.add(word.strip(".,;:"))

        for name in tech_names:
            entities.append(ExtractedEntity(entity_type="technology", value=name, confidence=0.65))

        return entities

    def extract_industries(self, papers: list[ArxivPaper], limit: int = 12) -> list[str]:
        full_text = " ".join(p.abstract + " " + p.title for p in papers).lower()
        found: list[str] = []
        for industry in INDUSTRY_KEYWORDS:
            if industry.lower() in full_text:
                found.append(industry.title() if industry.islower() else industry)
        return list(dict.fromkeys(found))[:limit]

    def extract_sub_technologies(
        self, papers: list[ArxivPaper], exclude: set[str] | None = None, limit: int = 12,
    ) -> list[str]:
        exclude = {e.lower() for e in (exclude or set())}
        full_text = " ".join(p.abstract + " " + p.title for p in papers).lower()
        found: list[str] = []
        for tech in TECHNOLOGY_KEYWORDS:
            if tech.lower() in full_text and tech.lower() not in exclude:
                found.append(tech)
        for paper in papers:
            if paper.technology.lower() not in exclude:
                found.append(paper.technology)
        return list(dict.fromkeys(found))[:limit]

    def extract_keywords(self, papers: list[ArxivPaper], top_n: int = 20) -> list[str]:
        stopwords = {
            "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
            "on", "by", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "this", "that",
            "these", "those", "from", "at", "as", "we", "our", "their",
            "its", "it", "which", "using", "based", "via", "also", "such",
            "paper", "propose", "proposed", "approach", "method", "results",
        }
        text = " ".join(p.abstract.lower() for p in papers)
        words = re.findall(r"\b[a-z]{4,}\b", text)
        filtered = [w for w in words if w not in stopwords]
        counts = Counter(filtered)
        return [word for word, _ in counts.most_common(top_n)]

    def compute_embeddings(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except Exception:
            return [self._simple_embedding(t) for t in texts]

    def _simple_embedding(self, text: str, dim: int = 64) -> list[float]:
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        return [h[i % len(h)] / 255.0 for i in range(dim)]
