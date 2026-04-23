"""
Embedding providers - abstraction for different embedding backends.
"""

from abc import ABC, abstractmethod
from typing import List

import requests


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        ...


class OllamaProvider(EmbeddingProvider):
    """
    Ollama embedding provider using /api/embeddings endpoint.

    Requires:
        - Ollama running with nomic-embed-text (or custom model)
        - CTX_OLLAMA_URL environment variable
    """

    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout: int = 30,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def dimension(self) -> int:
        # nomic-embed-text is 768-dim; if using a different model, override
        return 768

    def embed(self, text: str) -> List[float]:
        try:
            # Try new /api/embed endpoint first (Ollama >= 0.20)
            try:
                response = requests.post(
                    f"{self.url}/api/embed",
                    json={"model": self.model, "input": text},
                    timeout=self.timeout,
                )
                if response.status_code == 404:
                    # Fall back to legacy /api/embeddings for older Ollama
                    response = requests.post(
                        f"{self.url}/api/embeddings",
                        json={"model": self.model, "prompt": text},
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    return response.json()["embedding"]
                response.raise_for_status()
                return response.json()["embeddings"][0]
            except KeyError:
                # Fallback: try legacy response format
                return response.json()["embedding"]
        except requests.exceptions.RequestException as e:
            raise EmbeddingError(f"Failed to get embedding from Ollama: {e}") from e


class OpenAIProvider(EmbeddingProvider):
    """
    OpenAI embedding provider (for future use with text-embedding-3 models).

    Requires:
        - OPENAI_API_KEY environment variable
        - openai package installed
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = None

    @property
    def dimension(self) -> int:
        # text-embedding-3-small = 1536, text-embedding-3-large = 3072
        dims = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}
        return dims.get(self.model, 1536)

    def embed(self, text: str) -> List[float]:
        try:
            from openai import OpenAI
        except ImportError:
            raise EmbeddingError("openai package not installed. Run: pip install openai")

        if self._client is None:
            self._client = OpenAI()

        response = self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
    pass
