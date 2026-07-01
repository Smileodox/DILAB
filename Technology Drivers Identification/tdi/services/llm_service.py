import asyncio
import json
import re
import time
import httpx
from tdi.config import get_settings
from tdi.models.schemas import (
    AffectedIndustry,
    ClassificationResult,
    FutureScenario,
    IndustryTechnology,
    SubCategoryAssignment,
    TechnologyCategory,
)

VALID_RELATIONSHIPS = frozenset({
    "enables", "depends_on", "coexists_with", "influences", "interferes_with",
})
VALID_DIRECTIONS = frozenset({
    "affects_main", "affected_by_main", "bidirectional", "is_main",
})

_llm_semaphore = asyncio.Semaphore(1)

# Reference taxonomy inspired by Lee et al. (2022) TOD framework — Table B1 / Table 3
REFERENCE_CATEGORIES = [
    "AI/Big Data",
    "6G & Wireless Communication",
    "Spectrum & RF Systems",
    "Satellite & NTN",
    "Service Platform",
    "O2O Service",
    "Fintech",
    "Bio/Healthcare",
    "Smart City / IoT",
    "Cybersecurity",
    "Edge & Cloud Computing",
    "Defense & Aerospace",
]

INDUSTRY_TECH_HINTS: dict[str, list[str]] = {
    "telecommunications": ["Open RAN", "5G Core", "Network Slicing", "Massive MIMO"],
    "defense": ["Cognitive Radio", "Military SATCOM", "Electronic warfare systems", "Secure tactical radio"],
    "aerospace": ["Avionics datalink", "Satellite payloads", "UAV communication", "Air-to-ground links"],
    "satellite": ["LEO satellite communication", "Non-terrestrial networks", "Ground segment systems"],
    "broadcasting": ["Terrestrial broadcast systems", "Media delivery platforms", "DVB transmission"],
    "smart cities": ["Urban IoT networks", "Smart metering", "Municipal connectivity platforms"],
    "automotive": ["V2X communication", "Connected vehicle platforms", "Automotive radar"],
    "healthcare": ["Medical IoT", "Remote patient monitoring", "Hospital wireless systems"],
    "fintech": ["Mobile payment platforms", "Digital banking systems", "Fraud detection AI"],
    "energy": ["Smart grid communication", "AMI metering", "Utility private networks"],
    "transportation": ["Rail communication systems", "Logistics tracking", "Port automation"],
    "mining": ["Industrial IoT", "Private LTE networks", "Remote operations systems"],
    "utilities": ["Smart grid", "SCADA wireless", "Field area networks"],
}


class LLMService:
    def __init__(self):
        self.settings = get_settings()
        self._last_request_at: float = 0.0

    async def _wait_for_rate_limit(self) -> None:
        delay = self.settings.llm_request_delay
        if delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)

    async def _chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> str:
        if not self.settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        max_tokens = max_tokens or self.settings.llm_max_tokens
        last_error: Exception | None = None

        async with _llm_semaphore:
            for attempt in range(self.settings.llm_max_retries):
                await self._wait_for_rate_limit()

                async with httpx.AsyncClient(timeout=120.0) as client:
                    try:
                        response = await client.post(
                            f"{self.settings.openrouter_base_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                                "Content-Type": "application/json",
                                "HTTP-Referer": "http://localhost:8000",
                                "X-Title": self.settings.app_name,
                            },
                            json={
                                "model": self.settings.llm_model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                            },
                        )
                        self._last_request_at = time.monotonic()

                        if response.status_code == 429:
                            wait = float(response.headers.get("Retry-After", 0)) or self.settings.llm_retry_base_delay * (2 ** attempt)
                            last_error = httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
                            if attempt < self.settings.llm_max_retries - 1:
                                await asyncio.sleep(min(wait, 60))
                                continue
                            raise last_error

                        response.raise_for_status()
                        data = response.json()
                        content = self._parse_response_content(data)
                        if not content:
                            raise ValueError("LLM returned empty response")
                        return content

                    except httpx.HTTPStatusError as e:
                        last_error = e
                        if e.response.status_code in (429, 503) and attempt < self.settings.llm_max_retries - 1:
                            await asyncio.sleep(min(self.settings.llm_retry_base_delay * (2 ** attempt), 60))
                            continue
                        raise

        raise last_error or RuntimeError("LLM request failed")

    def _parse_response_content(self, data: dict) -> str:
        message = data.get("choices", [{}])[0].get("message", {})
        parts = [
            message.get("content"),
            message.get("reasoning"),
            message.get("text"),
        ]
        combined = "\n".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
        return combined

    def _extract_json(self, text: str | None) -> dict:
        if not text:
            raise ValueError("Empty LLM response")
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1)
        else:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                text = match.group(0)
        return json.loads(text.strip())

    def _clamp_confidence(self, value: object, default: float = 0.5) -> float:
        try:
            v = float(value)
            return round(min(max(v, 0.05), 0.99), 3)
        except (TypeError, ValueError):
            return default

    def _normalize_relationship(self, value: object) -> str:
        rel = str(value or "coexists_with").strip().lower().replace(" ", "_")
        aliases = {
            "enable": "enables", "enabling": "enables", "supports": "enables",
            "depend": "depends_on", "dependency": "depends_on", "requires": "depends_on",
            "coexist": "coexists_with", "complementary": "coexists_with",
            "influence": "influences", "regulates": "influences", "impacts": "influences",
            "interfere": "interferes_with", "conflicts": "interferes_with",
        }
        rel = aliases.get(rel, rel)
        return rel if rel in VALID_RELATIONSHIPS else "coexists_with"

    def _normalize_direction(self, value: object, sub_name: str, primary: str) -> str:
        if sub_name.lower() == primary.lower():
            return "is_main"
        d = str(value or "bidirectional").strip().lower().replace(" ", "_")
        aliases = {
            "affects_m": "affects_main", "affects_main_technology": "affects_main",
            "influences_main": "affects_main", "enables_main": "affects_main",
            "affected_by_m": "affected_by_main", "influenced_by_main": "affected_by_main",
            "mutual": "bidirectional", "both": "bidirectional", "two_way": "bidirectional",
            "main": "is_main", "self": "is_main",
        }
        d = aliases.get(d, d)
        return d if d in VALID_DIRECTIONS else "bidirectional"

    def _infer_relationship_to_main(
        self, sub_name: str, primary: str, category: str = "",
    ) -> tuple[str, str]:
        if sub_name.lower() == primary.lower():
            return "coexists_with", "is_main"

        s = sub_name.lower()
        p = primary.lower()

        if any(k in s for k in ("interfere", "conflict", "jamming", "contention")):
            return "interferes_with", "bidirectional"
        if any(k in s for k in ("depend", "require", "rely", "standard", "3gpp", "itu")):
            return "depends_on", "affected_by_main"
        if any(k in s for k in ("ai", "software", "analytics", "sensing", "mimo", "beamforming")):
            if any(k in p for k in ("spectrum", "sharing", "radio")):
                return "enables", "affects_main"
        if any(k in s for k in ("open ran", "network slicing", "6g", "ntn", "satellite")):
            if "spectrum" in p or "sharing" in p:
                return "influences", "bidirectional"
        if any(k in s for k in ("regulation", "policy", "licensing", "compliance")):
            return "influences", "affected_by_main"
        if any(k in s for k in ("platform", "service", "fintech", "o2o")):
            return "coexists_with", "affects_main"

        return "coexists_with", "bidirectional"

    def _enrich_subcategory_relationships(
        self, categories: list[TechnologyCategory], primary: str,
    ) -> list[TechnologyCategory]:
        enriched: list[TechnologyCategory] = []
        for cat in categories:
            subs: list[SubCategoryAssignment] = []
            for sub in cat.subcategories:
                rel = sub.relationship
                direction = sub.direction
                if rel == "coexists_with" and direction == "bidirectional":
                    inf_rel, inf_dir = self._infer_relationship_to_main(
                        sub.name, primary, cat.name,
                    )
                    rel, direction = inf_rel, inf_dir
                elif sub.name.lower() == primary.lower():
                    rel, direction = "coexists_with", "is_main"
                subs.append(sub.model_copy(update={
                    "relationship": self._normalize_relationship(rel),
                    "direction": self._normalize_direction(direction, sub.name, primary),
                }))
            enriched.append(cat.model_copy(update={"subcategories": subs}))
        return enriched

    def _parse_subcategories(
        self, raw: object, limit: int, primary: str = "",
    ) -> list[SubCategoryAssignment]:
        if not isinstance(raw, list):
            return []
        out: list[SubCategoryAssignment] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                name = item.strip()
                rel, direction = self._infer_relationship_to_main(name, primary)
                out.append(SubCategoryAssignment(
                    name=name, confidence=0.5, relationship=rel, direction=direction,
                ))
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("subcategory") or "").strip()
                if name:
                    rel = self._normalize_relationship(
                        item.get("relationship") or item.get("relation"),
                    )
                    direction = self._normalize_direction(
                        item.get("direction") or item.get("impact_direction"),
                        name, primary,
                    )
                    if rel == "coexists_with" and direction == "bidirectional" and not item.get("relationship"):
                        rel, direction = self._infer_relationship_to_main(name, primary)
                    out.append(SubCategoryAssignment(
                        name=name,
                        confidence=self._clamp_confidence(item.get("confidence"), 0.5),
                        relationship=rel,
                        direction=direction,
                    ))
            if len(out) >= limit:
                break
        return out

    def _parse_technology_categories(
        self, raw: object, max_categories: int, max_subs: int, primary: str = "",
    ) -> list[TechnologyCategory]:
        if not isinstance(raw, list):
            return []

        categories: list[TechnologyCategory] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("category") or "").strip()
            if not name:
                continue
            subs = self._parse_subcategories(
                item.get("subcategories") or item.get("sub_categories"),
                max_subs, primary,
            )
            categories.append(TechnologyCategory(
                name=name,
                confidence=self._clamp_confidence(item.get("confidence"), 0.5),
                subcategories=subs,
            ))
            if len(categories) >= max_categories:
                break
        return categories

    def _flatten_subcategories(self, categories: list[TechnologyCategory]) -> list[str]:
        seen: set[str] = set()
        flat: list[str] = []
        for cat in categories:
            for sub in cat.subcategories:
                key = sub.name.lower()
                if key not in seen:
                    seen.add(key)
                    flat.append(sub.name)
        return flat

    def _parse_industry_technologies(
        self, raw: object, limit: int, primary: str, industry: str = "",
    ) -> list[IndustryTechnology]:
        if not isinstance(raw, list):
            return []
        out: list[IndustryTechnology] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                name = item.strip()
                rel, direction = self._infer_relationship_to_main(name, primary, industry)
                out.append(IndustryTechnology(
                    name=name, confidence=0.5, relationship=rel, direction=direction,
                ))
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("technology") or "").strip()
                if not name:
                    continue
                rel = self._normalize_relationship(item.get("relationship") or item.get("relation"))
                direction = self._normalize_direction(
                    item.get("direction") or item.get("impact_direction"), name, primary,
                )
                if rel == "coexists_with" and direction == "bidirectional" and not item.get("relationship"):
                    rel, direction = self._infer_relationship_to_main(name, primary, industry)
                out.append(IndustryTechnology(
                    name=name,
                    confidence=self._clamp_confidence(item.get("confidence"), 0.5),
                    relationship=rel,
                    direction=direction,
                ))
            if len(out) >= limit:
                break
        return out

    def _parse_affected_industries(
        self, raw: object, max_industries: int, max_techs: int, primary: str,
    ) -> list[AffectedIndustry]:
        if not isinstance(raw, list):
            return []

        industries: list[AffectedIndustry] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                industries.append(AffectedIndustry(
                    name=item.strip(),
                    confidence=0.5,
                    technologies=[],
                ))
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("industry") or "").strip()
                if not name:
                    continue
                techs = self._parse_industry_technologies(
                    item.get("technologies") or item.get("related_technologies"),
                    max_techs,
                    primary,
                    name,
                )
                industries.append(AffectedIndustry(
                    name=name,
                    confidence=self._clamp_confidence(item.get("confidence"), 0.5),
                    technologies=techs,
                    is_main=bool(item.get("is_main") or item.get("main")),
                ))
            if len(industries) >= max_industries:
                break
        return industries

    def _hint_technologies_for_industry(self, industry: str) -> list[str]:
        key = industry.lower().strip()
        for hint_key, techs in INDUSTRY_TECH_HINTS.items():
            if hint_key in key or key in hint_key:
                return techs
        return []

    def _assign_technologies_to_industry(
        self,
        industry: AffectedIndustry,
        primary: str,
        pool: list[str],
        max_techs: int,
    ) -> AffectedIndustry:
        if industry.technologies:
            enriched = [
                t.model_copy(update={
                    "relationship": self._normalize_relationship(t.relationship),
                    "direction": self._normalize_direction(t.direction, t.name, primary),
                })
                for t in industry.technologies
            ]
            return industry.model_copy(update={"technologies": enriched[:max_techs]})

        hints = self._hint_technologies_for_industry(industry.name)
        chosen: list[str] = []
        primary_lower = primary.lower()
        for tech in hints + pool:
            if tech.lower() == primary_lower:
                continue
            if tech.lower() not in {c.lower() for c in chosen}:
                chosen.append(tech)
            if len(chosen) >= max_techs:
                break

        technologies = []
        for idx, tech in enumerate(chosen):
            rel, direction = self._infer_relationship_to_main(tech, primary, industry.name)
            technologies.append(IndustryTechnology(
                name=tech,
                confidence=round(max(0.55, 0.82 - idx * 0.05), 3),
                relationship=rel,
                direction=direction,
            ))
        return industry.model_copy(update={"technologies": technologies})

    def _infer_main_industry(self, result: ClassificationResult) -> str:
        if result.main_industry.strip():
            return result.main_industry.strip()

        for ind in result.affected_industries:
            if ind.is_main:
                return ind.name.strip()

        if result.affected_industries:
            return result.affected_industries[0].name.strip()

        if result.related_industries:
            return result.related_industries[0].strip()

        text = (
            f"{result.query_intent} {result.regulatory_domain} "
            f"{result.primary_technology} {result.primary_category}"
        ).lower()
        rules = [
            (("telecom", "spectrum", "5g", "6g", "wireless", "ran", "open ran"), "telecommunications"),
            (("defense", "military", "aerospace"), "defense"),
            (("broadcast", "media", "television"), "broadcasting"),
            (("satellite", "ntn", "space"), "satellite"),
            (("smart city", "iot", "urban"), "smart cities"),
            (("health", "medical", "hospital"), "healthcare"),
            (("fintech", "banking", "payment"), "fintech"),
            (("energy", "utility", "grid"), "utilities"),
            (("transport", "rail", "automotive"), "transportation"),
        ]
        for keywords, industry in rules:
            if any(k in text for k in keywords):
                return industry
        return "telecommunications"

    def ensure_affected_industries(self, result: ClassificationResult) -> ClassificationResult:
        """Ensure exactly one main industry; related industries listed separately."""
        settings = get_settings()
        primary = result.primary_technology.strip()
        max_techs = settings.max_technologies_per_industry
        pool = self._flatten_subcategories(result.technology_categories)
        pool = list(dict.fromkeys(
            pool + [t for t in result.related_technologies if t.strip() and t.lower() != primary.lower()],
        ))

        main_name = self._infer_main_industry(result)

        candidates = list(result.affected_industries)
        if not candidates and result.related_industries:
            candidates = [
                AffectedIndustry(name=name, confidence=0.75, technologies=[], is_main=False)
                for name in result.related_industries
            ]

        if not any(c.name.lower() == main_name.lower() for c in candidates):
            candidates.insert(0, AffectedIndustry(
                name=main_name, confidence=0.88, technologies=[], is_main=True,
            ))

        enriched_all = [
            self._assign_technologies_to_industry(ind, primary, pool, max_techs)
            for ind in candidates
        ]

        main_entry: AffectedIndustry | None = None
        related_entries: list[AffectedIndustry] = []

        for ind in enriched_all:
            if ind.name.lower() == main_name.lower():
                main_entry = ind.model_copy(update={"is_main": True, "confidence": max(ind.confidence, 0.85)})
            else:
                related_entries.append(ind.model_copy(update={"is_main": False}))

        if not main_entry:
            main_entry = self._assign_technologies_to_industry(
                AffectedIndustry(name=main_name, confidence=0.88, technologies=[], is_main=True),
                primary, pool, max_techs,
            )

        if not related_entries:
            for name in INDUSTRY_TECH_HINTS:
                if name.lower() == main_name.lower():
                    continue
                related_entries.append(
                    self._assign_technologies_to_industry(
                        AffectedIndustry(name=name.title(), confidence=0.72, technologies=[], is_main=False),
                        primary, pool, max_techs,
                    )
                )
                if len(related_entries) >= max(1, settings.max_industries - 1):
                    break

        related_entries = [ind for ind in related_entries if ind.technologies][
            : max(1, settings.max_industries - 1)
        ]
        related_industries = [ind.name for ind in related_entries]

        main_tech_names = {t.name.lower() for t in main_entry.technologies}
        industry_techs = [t.name for ind in related_entries for t in ind.technologies]
        related_technologies = list(dict.fromkeys(
            [primary]
            + [t.name for t in main_entry.technologies]
            + industry_techs
            + [t for t in pool if t.lower() != primary.lower() and t.lower() not in main_tech_names],
        ))[: settings.max_technologies]

        return result.model_copy(update={
            "main_industry": main_name,
            "main_industry_technologies": main_entry.technologies,
            "affected_industries": related_entries,
            "related_industries": related_industries,
            "related_technologies": related_technologies,
        })

    def _ensure_primary_in_hierarchy(
        self,
        primary: str,
        primary_category: str,
        categories: list[TechnologyCategory],
        max_subs: int,
    ) -> list[TechnologyCategory]:
        if not primary:
            return categories

        primary_lower = primary.lower()
        found_cat_idx: int | None = None
        found_sub_idx: int | None = None

        for ci, cat in enumerate(categories):
            for si, sub in enumerate(cat.subcategories):
                if sub.name.lower() == primary_lower:
                    found_cat_idx, found_sub_idx = ci, si
                    break
            if found_cat_idx is not None:
                break

        if found_cat_idx is not None and found_sub_idx is not None:
            sub = categories[found_cat_idx].subcategories.pop(found_sub_idx)
            sub = sub.model_copy(update={
                "confidence": max(sub.confidence, 0.9),
                "relationship": "coexists_with",
                "direction": "is_main",
            })
            categories[found_cat_idx].subcategories.insert(0, sub)
            categories[found_cat_idx].confidence = max(categories[found_cat_idx].confidence, 0.85)
            if not primary_category:
                primary_category = categories[found_cat_idx].name
            return categories

        parent = primary_category or "Spectrum & RF Systems"
        parent_idx = next((i for i, c in enumerate(categories) if c.name.lower() == parent.lower()), None)

        primary_sub = SubCategoryAssignment(
            name=primary, confidence=0.92,
            relationship="coexists_with", direction="is_main",
        )
        if parent_idx is not None:
            categories[parent_idx].subcategories = [
                primary_sub,
                *[s for s in categories[parent_idx].subcategories if s.name.lower() != primary_lower],
            ][:max_subs]
            categories[parent_idx].confidence = max(categories[parent_idx].confidence, 0.85)
        else:
            categories.insert(0, TechnologyCategory(
                name=parent,
                confidence=0.88,
                subcategories=[primary_sub],
            ))
        return categories[: self.settings.max_technology_categories]

    def _normalize_classification(self, data: dict, query: str) -> dict:
        settings = get_settings()

        def as_str(value: object, default: str = "") -> str:
            if value is None:
                return default
            return str(value).strip()

        def as_str_list(value: object, limit: int) -> list[str]:
            if not isinstance(value, list):
                return []
            return [as_str(item) for item in value if as_str(item)][:limit]

        primary = as_str(data.get("primary_technology"), query[:80])
        primary_category = as_str(data.get("primary_category"), "")

        categories = self._parse_technology_categories(
            data.get("technology_categories"),
            settings.max_technology_categories,
            settings.max_subcategories_per_category,
            primary,
        )
        categories = self._ensure_primary_in_hierarchy(
            primary, primary_category, categories, settings.max_subcategories_per_category,
        )
        categories = self._enrich_subcategory_relationships(categories, primary)

        if not primary_category and categories:
            for cat in categories:
                if any(s.name.lower() == primary.lower() for s in cat.subcategories):
                    primary_category = cat.name
                    break
            if not primary_category:
                primary_category = categories[0].name

        flat_subs = self._flatten_subcategories(categories)
        legacy_subs = as_str_list(data.get("related_technologies"), settings.max_technologies)
        related_technologies = flat_subs or legacy_subs
        if primary and primary.lower() not in {t.lower() for t in related_technologies}:
            related_technologies = [primary] + related_technologies

        affected_industries = self._parse_affected_industries(
            data.get("affected_industries"),
            settings.max_industries,
            settings.max_technologies_per_industry,
            primary,
        )
        if not affected_industries:
            affected_industries = self._parse_affected_industries(
                data.get("related_industries"),
                settings.max_industries,
                settings.max_technologies_per_industry,
                primary,
            )

        main_industry = as_str(data.get("main_industry"), "")
        if not main_industry:
            for ind in affected_industries:
                if ind.is_main:
                    main_industry = ind.name
                    break

        related_industries = (
            [ind.name for ind in affected_industries if not ind.is_main]
            if affected_industries
            else as_str_list(data.get("related_industries"), settings.max_industries)
        )

        return {
            "regulatory_domain": as_str(data.get("regulatory_domain"), "spectrum regulation"),
            "primary_technology": primary,
            "primary_category": primary_category,
            "main_industry": main_industry,
            "related_technologies": related_technologies[: settings.max_technologies],
            "related_industries": related_industries[: settings.max_industries],
            "query_intent": as_str(data.get("query_intent"), query[:200]),
            "technology_categories": [c.model_dump() for c in categories],
            "affected_industries": [ind.model_dump() for ind in affected_industries],
        }

    def _fallback_classification(self, query: str) -> ClassificationResult:
        q = query.lower()
        if "6g" in q or "ai" in q:
            primary = "AI-native 6G RAN"
            primary_cat = "6G & Wireless Communication"
            categories = [
                TechnologyCategory(name="6G & Wireless Communication", confidence=0.91, subcategories=[
                    SubCategoryAssignment(name="AI-native 6G RAN", confidence=0.92),
                    SubCategoryAssignment(name="Open RAN", confidence=0.78),
                    SubCategoryAssignment(name="Massive MIMO", confidence=0.74),
                ]),
                TechnologyCategory(name="AI/Big Data", confidence=0.86, subcategories=[
                    SubCategoryAssignment(name="AI Software", confidence=0.80),
                    SubCategoryAssignment(name="Human-AI collaboration system", confidence=0.72),
                    SubCategoryAssignment(name="Big data software", confidence=0.70),
                ]),
                TechnologyCategory(name="Spectrum & RF Systems", confidence=0.84, subcategories=[
                    SubCategoryAssignment(name="Dynamic Spectrum Sharing", confidence=0.83),
                    SubCategoryAssignment(name="Cognitive Radio", confidence=0.76),
                ]),
            ]
        elif "spectrum" in q or "sharing" in q:
            primary = "Dynamic Spectrum Sharing"
            primary_cat = "Spectrum & RF Systems"
            categories = [
                TechnologyCategory(name="Spectrum & RF Systems", confidence=0.93, subcategories=[
                    SubCategoryAssignment(name="Dynamic Spectrum Sharing", confidence=0.92),
                    SubCategoryAssignment(name="Cognitive Radio", confidence=0.81),
                    SubCategoryAssignment(name="Spectrum sensing", confidence=0.75),
                ]),
                TechnologyCategory(name="6G & Wireless Communication", confidence=0.82, subcategories=[
                    SubCategoryAssignment(name="Open RAN", confidence=0.77),
                    SubCategoryAssignment(name="Network Slicing", confidence=0.73),
                ]),
                TechnologyCategory(name="Satellite & NTN", confidence=0.76, subcategories=[
                    SubCategoryAssignment(name="Non-terrestrial networks", confidence=0.74),
                    SubCategoryAssignment(name="LEO satellite communication", confidence=0.68),
                ]),
            ]
        else:
            primary = query.split("?")[0][:80]
            primary_cat = "Spectrum & RF Systems"
            categories = [
                TechnologyCategory(name=primary_cat, confidence=0.88, subcategories=[
                    SubCategoryAssignment(name=primary, confidence=0.90),
                    SubCategoryAssignment(name="Dynamic Spectrum Sharing", confidence=0.75),
                ]),
                TechnologyCategory(name="AI/Big Data", confidence=0.80, subcategories=[
                    SubCategoryAssignment(name="Big data software", confidence=0.72),
                    SubCategoryAssignment(name="AI Software", confidence=0.70),
                ]),
            ]

        flat = self._flatten_subcategories(categories)
        result = ClassificationResult(
            regulatory_domain="spectrum regulation",
            primary_technology=primary,
            primary_category=primary_cat,
            related_technologies=flat[: self.settings.max_technologies],
            related_industries=[
                "telecommunications", "defense", "aerospace", "satellite",
                "broadcasting", "smart cities",
            ],
            query_intent=query[:200],
            technology_categories=categories,
            affected_industries=[],
        )
        return self.ensure_affected_industries(self.ensure_hierarchy(result))

    async def classify_query(self, query: str) -> ClassificationResult:
        settings = get_settings()
        ref_cats = ", ".join(REFERENCE_CATEGORIES[:8])
        user = (
            f'Query: "{query}"\n\n'
            "Task: Hierarchical technology classification (Lee et al. 2022 TOD framework).\n"
            f"Step 1 — Assign up to {settings.max_technology_categories} Categories (upper-level technology fields).\n"
            f"Step 2 — For EACH category, assign up to {settings.max_subcategories_per_category} Subcategories (specific technologies). "
            "Subcategories MUST belong to their parent category only.\n"
            "Step 3 — Set primary_technology = the main subcategory (M) from the query; "
            "primary_category = its parent category.\n"
            "Step 4 — For EACH subcategory, define its relationship to M:\n"
            "  - relationship: enables | depends_on | coexists_with | influences | interferes_with\n"
            "  - direction: affects_main (ST → M) | affected_by_main (M → ST) | bidirectional | is_main (only for M)\n"
            f"Step 5 — Set main_industry = the single primary industry sector for this query (e.g. telecommunications).\n"
            f"Step 6 — List up to {settings.max_industries - 1} RELATED industry sectors (not the main industry). "
            f"For EACH related industry, assign up to {settings.max_technologies_per_industry} technologies "
            "that affect or are affected by M (with relationship + direction).\n\n"
            f"Reference categories (use similar naming): {ref_cats}\n"
            "Example subcategories: AI Software, Big data software, Human-AI collaboration system, "
            "Dynamic Spectrum Sharing, Open RAN, SNS platform, Fintech big data analysis system.\n\n"
            "Return JSON only:\n"
            '{"regulatory_domain":"","primary_technology":"","primary_category":"",'
            '"query_intent":"",'
            '"technology_categories":[{"name":"Category","confidence":0.85,'
            '"subcategories":[{"name":"Subcategory","confidence":0.78,'
            '"relationship":"enables","direction":"affects_main"}]}],'
            '"main_industry":"telecommunications",'
            '"affected_industries":[{"name":"defense","is_main":false,"confidence":0.82,'
            '"technologies":[{"name":"Military SATCOM","confidence":0.78,'
            '"relationship":"influences","direction":"bidirectional"}]}]}'
        )

        try:
            raw = await self._chat(
                (
                    "Technology opportunity discovery (TOD) analyst. "
                    "Assign hierarchical Category → Subcategory labels with confidence 0-1. "
                    "For each subcategory and each industry-specific technology, specify how it affects "
                    "or is affected by the main technology M. JSON only, no prose."
                ),
                user,
                max_tokens=1400,
            )
            data = self._normalize_classification(self._extract_json(raw), query)
            result = ClassificationResult(**data)
            result = self.ensure_hierarchy(result)
            return self.ensure_affected_industries(result)
        except Exception:
            return self._fallback_classification(query)

    def _format_link_to_main(self, name: str, relationship: str, direction: str, main_name: str) -> str:
        if direction == "is_main":
            return f"{name} (Main Technology M)"
        if direction == "affects_main":
            return f"{name} —[{relationship}]→ {main_name}"
        if direction == "affected_by_main":
            return f"{main_name} —[{relationship}]→ {name}"
        return f"{name} ↔ {main_name} ({relationship})"

    def to_classification_json(self, classification: ClassificationResult) -> dict:
        classification = self.ensure_affected_industries(self.ensure_hierarchy(classification))
        return {
            "regulatory_domain": classification.regulatory_domain,
            "primary_technology": classification.primary_technology,
            "primary_category": classification.primary_category,
            "main_industry": classification.main_industry,
            "main_industry_technologies": [
                {
                    "name": tech.name,
                    "confidence": tech.confidence,
                    "relationship": tech.relationship,
                    "direction": tech.direction,
                    "link_to_main": self._format_link_to_main(
                        tech.name, tech.relationship, tech.direction, classification.primary_technology,
                    ),
                }
                for tech in classification.main_industry_technologies
            ],
            "query_intent": classification.query_intent,
            "technology_categories": [
                {
                    "category": cat.name,
                    "confidence": cat.confidence,
                    "subcategories": [
                        {
                            "name": sub.name,
                            "confidence": sub.confidence,
                            "relationship": sub.relationship,
                            "direction": sub.direction,
                            "link_to_main": (
                                f"{sub.name} —[{sub.relationship}]→ M"
                                if sub.direction == "affects_main"
                                else f"M —[{sub.relationship}]→ {sub.name}"
                                if sub.direction == "affected_by_main"
                                else f"{sub.name} ↔ M ({sub.relationship})"
                                if sub.direction == "bidirectional"
                                else f"{sub.name} (Main Technology M)"
                            ),
                        }
                        for sub in cat.subcategories
                    ],
                }
                for cat in classification.technology_categories
            ],
            "related_industries": classification.related_industries,
            "affected_industries": [
                {
                    "industry": ind.name,
                    "confidence": ind.confidence,
                    "technologies": [
                        {
                            "name": tech.name,
                            "confidence": tech.confidence,
                            "relationship": tech.relationship,
                            "direction": tech.direction,
                            "link_to_main": (
                                f"{tech.name} —[{tech.relationship}]→ M"
                                if tech.direction == "affects_main"
                                else f"M —[{tech.relationship}]→ {tech.name}"
                                if tech.direction == "affected_by_main"
                                else f"{tech.name} ↔ M ({tech.relationship})"
                                if tech.direction == "bidirectional"
                                else f"{tech.name} (Main Technology M)"
                            ),
                        }
                        for tech in ind.technologies
                    ],
                }
                for ind in classification.affected_industries
            ],
            "related_technologies_flat": classification.related_technologies,
        }

    def ensure_hierarchy(self, result: ClassificationResult) -> ClassificationResult:
        """Guarantee non-empty Category → Subcategory hierarchy for dashboard JSON."""
        primary = result.primary_technology.strip()

        if result.technology_categories:
            if not result.primary_category:
                for cat in result.technology_categories:
                    if any(
                        s.name.lower() == primary.lower()
                        for s in cat.subcategories
                    ):
                        result = result.model_copy(update={"primary_category": cat.name})
                        break
                if not result.primary_category:
                    result = result.model_copy(
                        update={"primary_category": result.technology_categories[0].name},
                    )
            enriched = self._enrich_subcategory_relationships(
                result.technology_categories, primary,
            )
            result = result.model_copy(update={"technology_categories": enriched})
            return self.ensure_affected_industries(result)

        primary = result.primary_technology.strip()
        primary_cat = result.primary_category.strip() or self._infer_category(primary, result.query_intent)
        techs = list(dict.fromkeys(
            [primary] + [t for t in result.related_technologies if t.strip()],
        ))[: self.settings.max_technologies]

        subcategories: list[SubCategoryAssignment] = []
        for idx, tech in enumerate(techs):
            conf = 0.92 if tech.lower() == primary.lower() else round(max(0.55, 0.86 - idx * 0.06), 3)
            rel, direction = self._infer_relationship_to_main(tech, primary, primary_cat)
            subcategories.append(SubCategoryAssignment(
                name=tech, confidence=conf, relationship=rel, direction=direction,
            ))

        secondary_cat = self._infer_secondary_category(techs, primary_cat)
        categories: list[TechnologyCategory] = [
            TechnologyCategory(
                name=primary_cat,
                confidence=0.88,
                subcategories=subcategories[: self.settings.max_subcategories_per_category],
            ),
        ]

        if secondary_cat and secondary_cat.lower() != primary_cat.lower():
            extra_subs = subcategories[self.settings.max_subcategories_per_category:]
            if extra_subs:
                categories.append(TechnologyCategory(
                    name=secondary_cat,
                    confidence=0.76,
                    subcategories=extra_subs[: self.settings.max_subcategories_per_category],
                ))

        result = result.model_copy(update={
            "primary_category": primary_cat,
            "technology_categories": categories,
        })
        return self.ensure_affected_industries(result)

    def _infer_category(self, primary: str, query_intent: str) -> str:
        text = f"{primary} {query_intent}".lower()
        rules = [
            (("spectrum", "sharing", "cognitive", "radio", "rf", "mmwave"), "Spectrum & RF Systems"),
            (("6g", "5g", "ran", "mimo", "ntn", "satellite", "terrestrial"), "6G & Wireless Communication"),
            (("ai", "machine learning", "big data", "nlp"), "AI/Big Data"),
            (("fintech", "payment", "banking"), "Fintech"),
            (("health", "bio", "medical"), "Bio/Healthcare"),
        ]
        for keywords, category in rules:
            if any(k in text for k in keywords):
                return category
        return "Spectrum & RF Systems"

    def _infer_secondary_category(self, techs: list[str], primary_cat: str) -> str:
        joined = " ".join(techs).lower()
        if primary_cat == "Spectrum & RF Systems" and any(k in joined for k in ("ai", "6g", "open ran")):
            return "6G & Wireless Communication"
        if primary_cat == "6G & Wireless Communication" and "spectrum" in joined:
            return "Spectrum & RF Systems"
        if "ai" in joined and primary_cat != "AI/Big Data":
            return "AI/Big Data"
        return ""

    async def explain_scenarios_batch(
        self,
        scenarios: list[dict],
        papers: list[dict],
        signals: list[dict],
        target_year: int,
    ) -> dict[str, str]:
        if not scenarios:
            return {}

        compact = [
            {"id": s["id"], "title": s["title"][:60]}
            for s in scenarios
        ]
        signal_names = [s["name"] for s in signals[:3]]

        user = (
            f"Year {target_year}. Scenarios: {json.dumps(compact, separators=(',', ':'))}. "
            f"Signals: {signal_names}. "
            'Return JSON: {"explanations":{"<id>":"1 short paragraph each"}}'
        )

        try:
            raw = await self._chat(
                "Regulatory analyst. JSON only.",
                user,
                temperature=0.4,
                max_tokens=400,
            )
            return self._extract_json(raw).get("explanations", {})
        except Exception:
            return {s["id"]: s["description"] for s in scenarios}

    async def generate_recommendations(
        self,
        query: str,
        classification: ClassificationResult,
        scenarios: list[FutureScenario],
        signals: list[dict],
        target_year: int,
    ) -> list[str]:
        top_signals = [s["name"] for s in signals[:3]]
        top_scenarios = [s.title[:50] for s in scenarios[:2]]

        user = (
            f'Q: "{query[:120]}" | Year: {target_year} | '
            f'Tech: {classification.primary_technology} | '
            f'Category: {classification.primary_category} | '
            f'Domain: {classification.regulatory_domain} | '
            f'Signals: {top_signals} | Scenarios: {top_scenarios}\n'
            'Return JSON: {"recommendations":["4-5 short bullet recommendations"]}'
        )

        try:
            raw = await self._chat(
                "Spectrum policy advisor. JSON only.",
                user,
                max_tokens=400,
            )
            recs = self._extract_json(raw).get("recommendations", [])
            if recs:
                return recs[:5]
        except Exception:
            pass

        return self._fallback_recommendations(classification, signals, target_year)

    def _fallback_recommendations(
        self,
        classification: ClassificationResult,
        signals: list[dict],
        target_year: int,
    ) -> list[str]:
        top_signal = signals[0]["name"] if signals else classification.primary_technology
        return [
            f"Monitor {classification.primary_technology} ({classification.primary_category}) "
            f"in {classification.regulatory_domain} through {target_year}.",
            f"Prioritize regulatory sandboxes for {top_signal}.",
            f"Align spectrum policy with 3GPP/ITU-R timelines for {classification.primary_technology}.",
            "Strengthen cross-border spectrum sharing coordination.",
            f"Review licensing for: {', '.join(classification.related_technologies[:3])}.",
        ]
