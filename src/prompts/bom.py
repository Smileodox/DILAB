BOM_DECOMPOSE = """You are analyzing a component from {system}.

Parent context: {parent_context}
Component to decompose: {component_name}
Component description: {component_description}

Based ONLY on the following source material, identify the sub-components or sub-technologies of this component.

SOURCE MATERIAL:
{rag_chunks}

Return JSON with this structure:
{{
  "components": [
    {{
      "name": "component name",
      "description": "brief technical description",
      "is_leaf": true/false (true if this is a fundamental technology or material)
    }}
  ],
  "source_chunk_ids_used": ["chunk_id_1", "chunk_id_2"]
}}

Only include components you can support with the provided source material. If the source material doesn't contain enough information, return fewer components rather than guessing."""


BOM_CLASSIFY_DRIVER = """Given this technology component from a {domain} product BOM:

Name: {name}
Description: {description}
BOM Path: {bom_path}

Is this a Technology Driver — meaning a technology with active R&D, expected performance improvements, or potential for disruption in the next 5-15 years?

Return JSON:
{{
  "is_tech_driver": true/false,
  "reasoning": "why or why not"
}}"""
