import json
import os
import re
from typing import Optional
from pr_reviewer.models import ReviewReport
from pr_reviewer.providers.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """LLM Provider using Google Gemini API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        super().__init__(model_name or os.environ.get("DEFAULT_MODEL", "gemini-2.0-flash"))
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def review_diff(
        self,
        diff_text: str,
        pr_context: str,
        system_instruction: str
    ) -> ReviewReport:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        user_prompt = f"""{system_instruction}

PR Identifier / Context:
{pr_context}

Pull Request Diff to Review:
{diff_text}

Provide your complete code review formatted strictly as valid JSON adhering to the following schema:
{json.dumps(ReviewReport.model_json_schema(), indent=2)}
"""

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_name or "gemini-2.0-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ReviewReport,
                ),
            )
            data = json.loads(response.text)
            return ReviewReport.model_validate(data)
        except Exception:
            # Fallback to direct HTTP request using httpx if google-genai is not yet installed or schema failed
            import httpx

            target_model = self.model_name or "gemini-2.0-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            with httpx.Client(timeout=60.0) as http_client:
                res = http_client.post(url, json=payload)
                res.raise_for_status()
                res_data = res.json()
                try:
                    text_content = res_data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    raise ValueError(f"Gemini API returned unexpected response: {res_data}")

                # Extract JSON if wrapped in markdown
                match = re.search(r"\{.*\}", text_content, re.DOTALL)
                clean_json = match.group(0) if match else text_content
                return ReviewReport.model_validate(json.loads(clean_json))
