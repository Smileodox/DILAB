"""Knowledge Base pipeline step.

Input: Source registry (URLs + fallback content)
Output: data/outputs/kb_state.json + ChromaDB collection

Owner: Branch 1 (feature/knowledge-base)
"""


def run(output_path: str = "data/outputs/kb_state.json") -> dict:
    raise NotImplementedError("TODO: Branch 1 — extract from notebooks/01_knowledge_base.ipynb")
