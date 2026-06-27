MERGE_DRIVERS = """You have two lists of technology drivers identified through different methods for the {domain} domain.

BOTTOM-UP DRIVERS (from product BOM decomposition):
{bom_drivers}

TOP-DOWN DRIVERS (from technology trend scanning):
{trend_drivers}

Map these lists onto each other:
1. Find matches: a BOM driver and a trend driver that describe the same or closely related technology
2. Identify BOM-only drivers: present in products but not flagged as trends
3. Identify trend-only drivers: emerging trends not yet in current products

CRITICAL RULE: Only match drivers of the SAME dimension type (shown in brackets).
Do NOT merge a hardware driver with a regulatory driver — those are independent
morphological dimensions, not duplicates. Cross-type relationships will be captured
in the CIB cross-impact matrix instead.

Return JSON:
{{
  "matches": [
    {{
      "bom_driver_id": "id",
      "trend_driver_id": "id",
      "unified_name": "best name for this driver",
      "reasoning": "why these are the same technology"
    }}
  ],
  "bom_only": ["list of bom driver ids with no trend match"],
  "trend_only": ["list of trend driver ids with no bom match"]
}}"""
