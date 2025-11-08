"""
Retrieval tool for searching and retrieving information.
"""

import logging
from typing import Any, Dict, List
from ..tools import BaseTool

logger = logging.getLogger(__name__)


class RetrievalTool(BaseTool):
    """Tool for retrieving information from various sources."""

    def __init__(self):
        self.knowledge_base = {
            "contract_law": "Contract law governs agreements between parties...",
            "regulatory_compliance": "Regulatory compliance involves adhering to laws...",
            "data_privacy": "Data privacy protects personal information...",
        }

    @property
    def name(self) -> str:
        return "retrieval"

    @property
    def description(self) -> str:
        return "Retrieves relevant information based on query"

    def run(self, input_data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve information based on query.

        Args:
            input_data: Dictionary containing 'query' and optional 'source' keys
            context: Execution context

        Returns:
            Retrieved information
        """
        try:
            query = input_data.get('query', '')
            source = input_data.get('source', 'knowledge_base')

            if not query:
                raise ValueError("query parameter is required")

            # Simple keyword-based retrieval (can be extended with vector search, etc.)
            results = self._search_knowledge_base(query)

            if not results:
                logger.warning(f"No results found for query: {query}")
                return {"results": [], "query": query, "found": False}

            logger.info(f"Retrieved {len(results)} results for query: {query}")
            return {
                "results": results,
                "query": query,
                "found": True,
                "count": len(results)
            }

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise

    def _search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """Search the knowledge base for relevant information."""
        results = []
        query_lower = query.lower()

        for topic, content in self.knowledge_base.items():
            if query_lower in topic.lower() or query_lower in content.lower():
                results.append({
                    "topic": topic,
                    "content": content,
                    "relevance_score": 1.0  # Simple scoring
                })

        return results
