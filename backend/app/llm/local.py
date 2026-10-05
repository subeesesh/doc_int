import httpx
import json
import logging
from typing import Optional
from app.llm.base import LLMProvider, LLMResponse
from app.config.settings import settings

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434')
        self.model = getattr(settings, 'LLM_MODEL', getattr(settings, 'OLLAMA_MODEL', 'qwen3:1.7b'))
        self.timeout = 120.0

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 2048) -> LLMResponse:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                return LLMResponse(
                    text=data.get("response", ""),
                    model=data.get("model", self.model),
                    provider="ollama",
                    usage={
                        "prompt_eval_count": data.get("prompt_eval_count", 0),
                        "eval_count": data.get("eval_count", 0)
                    }
                )
        except Exception as e:
            logger.error(f"Error generating text from Ollama: {e}")
            raise

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 2048) -> dict:
        json_prompt = prompt + "\n\nRespond in valid JSON only."
        response = await self.generate(
            prompt=json_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        text = response.text.strip()
        
        # Try to extract JSON if there's markdown wrapping
        if text.startswith("```json"):
            text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
        elif text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
        
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from Ollama. Response: {text[:100]}... Error: {e}")
            raise ValueError(f"Invalid JSON response: {e}")

    def is_available(self) -> bool:
        url = f"{self.base_url}/api/tags"
        try:
            # Sync check for availability since is_available is sync in base class
            with httpx.Client(timeout=2.0) as client:
                response = client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama is not available: {e}")
            return False
