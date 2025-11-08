"""
Context management for storing intermediate results and cross-step data passing.
"""

import logging
import time
from typing import Any, Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages context data across task execution steps."""

    def __init__(self, expiration_time: int = 3600):  # 1 hour default
        """
        Initialize context manager.

        Args:
            expiration_time: Time in seconds after which context data expires
        """
        self._context: Dict[str, Dict[str, Any]] = {}
        self._expiration_time = expiration_time
        self._lock = Lock()

    def set(self, key: str, value: Any, step_id: Optional[str] = None) -> None:
        """
        Set a value in the context.

        Args:
            key: Context key
            value: Value to store
            step_id: Optional step identifier
        """
        with self._lock:
            if step_id not in self._context:
                self._context[step_id or "global"] = {}

            self._context[step_id or "global"][key] = {
                "value": value,
                "timestamp": time.time(),
                "step_id": step_id
            }
            logger.debug(f"Set context key '{key}' for step '{step_id or 'global'}'")

    def get(self, key: str, step_id: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a value from the context.

        Args:
            key: Context key
            step_id: Optional step identifier
            default: Default value if key not found

        Returns:
            Context value or default
        """
        with self._lock:
            step_context = self._context.get(step_id or "global", {})
            entry = step_context.get(key)

            if entry:
                # Check expiration
                if time.time() - entry["timestamp"] > self._expiration_time:
                    logger.warning(f"Context key '{key}' has expired")
                    del step_context[key]
                    return default

                return entry["value"]

            return default

    def get_all(self, step_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all context data for a step.

        Args:
            step_id: Optional step identifier

        Returns:
            Dict of all context data
        """
        with self._lock:
            step_context = self._context.get(step_id or "global", {}).copy()

            # Remove expired entries
            current_time = time.time()
            expired_keys = [
                k for k, v in step_context.items()
                if current_time - v["timestamp"] > self._expiration_time
            ]

            for k in expired_keys:
                del step_context[k]
                logger.warning(f"Removed expired context key '{k}'")

            return {k: v["value"] for k, v in step_context.items()}

    def clear(self, step_id: Optional[str] = None) -> None:
        """
        Clear context data.

        Args:
            step_id: Optional step identifier (if None, clear all)
        """
        with self._lock:
            if step_id:
                self._context.pop(step_id, None)
                logger.info(f"Cleared context for step '{step_id}'")
            else:
                self._context.clear()
                logger.info("Cleared all context data")

    def cleanup_expired(self) -> int:
        """
        Clean up expired context entries.

        Returns:
            Number of entries cleaned up
        """
        with self._lock:
            current_time = time.time()
            cleaned_count = 0

            for step_id, step_context in list(self._context.items()):
                expired_keys = [
                    k for k, v in step_context.items()
                    if current_time - v["timestamp"] > self._expiration_time
                ]

                for k in expired_keys:
                    del step_context[k]
                    cleaned_count += 1

                # Remove empty step contexts
                if not step_context:
                    del self._context[step_id]

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired context entries")

            return cleaned_count
