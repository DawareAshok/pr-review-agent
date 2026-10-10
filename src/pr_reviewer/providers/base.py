from abc import ABC, abstractmethod
from typing import Optional
from pr_reviewer.models import ReviewReport


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name

    @abstractmethod
    def review_diff(
        self,
        diff_text: str,
        pr_context: str,
        system_instruction: str
    ) -> ReviewReport:
        """
        Submits diff and context to LLM and returns structured ReviewReport.
        """
        pass
