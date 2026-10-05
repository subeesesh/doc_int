from app.llm.base import LLMProvider
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

def get_llm_provider() -> LLMProvider:
    provider_type = getattr(settings, 'LLM_PROVIDER', 'local')
    if provider_type == 'bedrock':
        from app.llm.bedrock import BedrockProvider
        return BedrockProvider()
    elif provider_type == 'mock':
        from app.llm.mock import MockProvider
        return MockProvider()
    else:  # 'local' or default
        from app.llm.local import OllamaProvider
        provider = OllamaProvider()
        if not provider.is_available():
            logger.warning('Ollama not available, falling back to mock provider')
            from app.llm.mock import MockProvider
            return MockProvider()
        return provider
