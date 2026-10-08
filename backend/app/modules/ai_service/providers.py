import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class AIRiskProvider(ABC):
    @abstractmethod
    def evaluate(self, system_prompt: str, user_prompt: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        """
        Executes external API call to the LLM provider.
        Returns parsed JSON dict or raises an exception on failure.
        """
        pass

class GroqRiskProvider(AIRiskProvider):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", max_retries: int = 1):
        if not api_key:
            raise ValueError("Groq API key cannot be empty")
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        from groq import Groq
        self.client = Groq(api_key=api_key)

    def evaluate(self, system_prompt: str, user_prompt: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    timeout=float(timeout_seconds)
                )
                raw_text = completion.choices[0].message.content or ""
                return json.loads(raw_text)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1.0)
                    continue
        raise last_error or RuntimeError("Groq evaluation failed with unknown error")

class GeminiRiskProvider(AIRiskProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.8-flash", max_retries: int = 1):
        if not api_key:
            raise ValueError("Gemini API key cannot be empty")
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        import google.genai as genai
        self.client = genai.Client(api_key=api_key)

    def evaluate(self, system_prompt: str, user_prompt: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Combine system instructions and user prompt for high-compatibility across Gemini models
                combined_prompt = f"{system_prompt}\n\nIMPORTANT: Respond with pure JSON only without markdown formatting.\n\n{user_prompt}"
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=combined_prompt
                )
                raw_text = (response.text or "").strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                return json.loads(raw_text)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(1.5)
                    continue
        raise last_error or RuntimeError("Gemini evaluation failed with unknown error")
