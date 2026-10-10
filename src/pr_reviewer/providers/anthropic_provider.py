import json
import os
import re
from typing import Optional
from pr_reviewer.models import ReviewReport
from pr_reviewer.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """LLM Provider using Anthropic Claude API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        super().__init__(model_name or os.environ.get("DEFAULT_MODEL", "claude-3-5-sonnet-20241022"))
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def review_diff(
        self,
        diff_text: str,
        pr_context: str,
        system_instruction: str
    ) -> ReviewReport:
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package is not installed. Install it via 'pip install anthropic'")

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")

        client = anthropic.Anthropic(api_key=self.api_key)

        user_prompt = f"""PR Identifier / Context:
{pr_context}

Pull Request Diff to Review:
{diff_text}

Provide your code review strictly in valid JSON format matching this schema:
{json.dumps(ReviewReport.model_json_schema(), indent=2)}
Only output the raw JSON object, without backticks or surrounding text.
"""

        message = client.messages.create(
            model=self.model_name or "claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system_instruction,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        text_content = message.content[0].text
        # Remove any leading markdown fence
        cleaned = re.sub(r"^```(?:json)?\s*", "", text_content.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        json_str = match.group(0) if match else cleaned
        data = json.loads(json_str)
        return ReviewReport.model_validate(data)
