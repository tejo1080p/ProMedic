import os
from typing import Any

from langchain_core.embeddings import Embeddings


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


def get_chat_model() -> Any:
    if LLM_PROVIDER == "huggingface":
        from langchain_openai import ChatOpenAI

        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required when LLM_PROVIDER=huggingface.")
        return ChatOpenAI(
            model=LLM_MODEL,
            api_key=token,
            base_url=os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1"),
            temperature=0.2,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(model=LLM_MODEL)


class HuggingFaceEmbeddings(Embeddings):
    def __init__(self, model: str):
        from huggingface_hub import InferenceClient

        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required when LLM_PROVIDER=huggingface.")
        self.client = InferenceClient(token=token)
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        result = self.client.feature_extraction(text, model=self.model)
        if hasattr(result, "tolist"):
            result = result.tolist()
        if result and isinstance(result[0], list):
            result = [sum(values) / len(values) for values in zip(*result)]
        return [float(value) for value in result]


def get_embeddings() -> Embeddings:
    if LLM_PROVIDER == "huggingface":
        return HuggingFaceEmbeddings(EMBEDDING_MODEL)

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=EMBEDDING_MODEL)


def chat(messages: list[dict[str, str]], stream: bool = True):
    if LLM_PROVIDER == "huggingface":
        from huggingface_hub import InferenceClient

        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required when LLM_PROVIDER=huggingface.")
        client = InferenceClient(token=token)
        return client.chat_completion(
            messages=messages,
            model=LLM_MODEL,
            stream=stream,
            max_tokens=900,
            temperature=0.2,
        )

    import ollama

    return ollama.chat(model=LLM_MODEL, messages=messages, stream=stream)


def stream_text(response):
    for chunk in response:
        if hasattr(chunk, "choices"):
            content = chunk.choices[0].delta.content
        else:
            content = chunk["message"]["content"]
        if content:
            yield content