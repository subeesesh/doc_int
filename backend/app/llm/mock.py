from typing import Optional
from app.llm.base import LLMProvider, LLMResponse

class MockProvider(LLMProvider):
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 2048) -> LLMResponse:
        return LLMResponse(
            text="Mock LLM response",
            model="mock-model",
            provider="mock",
            usage={}
        )
        
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 2048) -> dict:
        return {
            'entities': [],
            'facts': [],
            'relationships': []
        }
        
    def is_available(self) -> bool:
        return True
