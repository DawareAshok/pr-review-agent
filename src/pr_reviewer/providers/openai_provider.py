import json
import os
import re
from typing import Optional
from pr_reviewer.models import ReviewReport
from pr_reviewer.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """LLM Provider using OpenAI API or OpenAI-compatible endpoints."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(model_name or os.environ.get("DEFAULT_MODEL", "gpt-4o-mini"))
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    def review_diff(
        self,
        diff_text: str,
        pr_context: str,
        system_instruction: str
    ) -> ReviewReport:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is not installed. Install it via 'pip install openai' or 'pip install -e .[openai]'"
            )

        if not self.api_key and not self.base_url:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

        client = OpenAI(
            api_key=self.api_key or "mock-key",
            base_url=self.base_url
        )

        user_prompt = f"""PR Identifier / Context:
{pr_context}

Pull Request Diff to Review:
{diff_text}

Provide your complete code review formatted strictly matching the ReviewReport schema."""

        try:
            # Use structured output parsing
            completion = client.beta.chat.completions.parse(
                model=self.model_name or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=ReviewReport,
            )
            report = completion.choices[0].message.parsed
            if not report:
                raise ValueError("Model failed to parse into ReviewReport schema.")
            return report
        except Exception:
            # Fallback to json_object mode if structured outputs fail
            schema_json = json.dumps(ReviewReport.model_json_schema(), indent=2)
            completion = client.chat.completions.create(
                model=self.model_name or "gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": f"{system_instruction}\nReturn strictly valid JSON conforming to this schema:\n{schema_json}"
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw_content = completion.choices[0].message.content or "{}"
            match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            clean_json = match.group(0) if match else raw_content
            data = json.loads(clean_json)
            return ReviewReport.model_validate(data)
