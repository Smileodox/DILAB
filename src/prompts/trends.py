TREND_SCAN = """You are scanning for technology trends relevant to regulatory frequency monitoring and spectrum management.

Based ONLY on the following source material, identify major technology trends that could impact this domain in the next 5-15 years.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "trends": [
    {{
      "name": "trend name",
      "description": "what is this trend",
      "relevance": "how does this impact regulatory frequency monitoring specifically",
      "timeframe": "near-term (0-5y) / mid-term (5-10y) / long-term (10-15y)"
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}

Only include trends supported by the source material."""


TREND_IMPACT = """Evaluate the impact of this technology trend on regulatory frequency monitoring:

Trend: {trend_name}
Description: {trend_description}

Based ONLY on the following source material, assess the impact.

SOURCE MATERIAL:
{rag_chunks}

Return JSON:
{{
  "impact_level": "high/medium/low/none",
  "impact_description": "specific ways this trend changes regulatory frequency monitoring",
  "affected_areas": ["list of product areas affected"],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}"""
