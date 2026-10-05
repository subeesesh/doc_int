from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional

class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    usage: dict = {}

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 2048) -> LLMResponse:
        pass
    
    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 2048) -> dict:
        """Generate and parse JSON response"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
