"""
Web analyzer tool.

Analyzes plain text (or HTML-derived text) and returns a summary,
keywords and discovered links.
"""
import re
from collections import Counter
from typing import Any, Dict, List

from ..registry import BaseTool, tool_registry


STOPWORDS = {
    "the", "and", "is", "in", "to", "of", "a", "for", "on", "with",
    "that", "this", "it", "as", "are", "was", "be", "by", "an",
}


class WebAnalyzerTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_analyzer"

    @property
    def description(self) -> str:
        return "Analyze text content: produce summary, keywords and links"

    def _extract_text(self, input_data: Any) -> str:
        if isinstance(input_data, dict):
            # Prefer explicit 'content' key
            content = input_data.get("content") or input_data.get("text")
            if content:
                return str(content)
            # fallback: serialize dict values
            return "\n".join(str(v) for v in input_data.values())
        return str(input_data)

    def _summarize(self, text: str, max_sentences: int = 3) -> str:
        # Simple heuristic: split by sentences and take first N non-empty
        sentences = [s.strip() for s in re.split(r'[\.\n]+', text) if s.strip()]
        if not sentences:
            return ""
        return " ".join(sentences[:max_sentences])

    def _keywords(self, text: str, top_k: int = 10) -> List[str]:
        words = re.findall(r"\b[\w']{4,}\b", text.lower())
        words = [w for w in words if w not in STOPWORDS]
        counts = Counter(words)
        return [w for w, _ in counts.most_common(top_k)]

    def _extract_links(self, text: str) -> List[str]:
        # Find http(s) links
        return re.findall(r'https?://[^\s)\]\}]+', text)

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        text = self._extract_text(input_data)
        summary = self._summarize(text)
        keywords = self._keywords(text)
        links = self._extract_links(text)

        return {
            "summary": summary,
            "keywords": keywords,
            "links": links,
            "length": len(text),
        }


# Register tool
try:
    tool_registry.register_tool("web_analyzer", WebAnalyzerTool)
except Exception:
    pass
