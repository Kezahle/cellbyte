from typing import List
import openai
from llm.base import LLMProvider, Message, LLMResponse

class OpenAIProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for OpenAI's API.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initializes the OpenAI client.
        """
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        
        self.client = openai.OpenAI(api_key=api_key, organization=None)        
        self.model = model

    def generate(self, messages: List[Message], temperature: float = 0.1, max_tokens: int = 4000) -> LLMResponse:
        """
        Generates a response using the OpenAI Chat Completions API.
        """
        try:
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
        except openai.APIError as e:
            print(f"An OpenAI API error occurred: {e}")
            raise

    def get_model_name(self) -> str:
        """
        Returns the configured model name.
        """
        return self.model