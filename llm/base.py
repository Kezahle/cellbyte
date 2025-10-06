from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class Message:
    """Represents a chat message."""
    role: str  # 'system', 'user', or 'assistant'
    content: str

@dataclass
class LLMResponse:
    """Represents a standardized LLM response."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None

class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    It defines the contract that any concrete LLM implementation must follow.
    """

    @abstractmethod
    def generate(self, messages: List[Message], temperature: float = 0.1, max_tokens: int = 4000) -> LLMResponse:
        """
        Generate a response from the LLM based on a list of messages.

        Args:
            messages: A list of Message objects representing the conversation history.
            temperature: The creativity of the response (0.0 to 1.0).
            max_tokens: The maximum number of tokens to generate.

        Returns:
            An LLMResponse object containing the generated content and metadata.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the name of the specific model being used by this provider.

        Returns:
            A string representing the model name (e.g., "gpt-4o-mini").
        """
        pass