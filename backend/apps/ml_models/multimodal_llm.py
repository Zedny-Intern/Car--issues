"""
LLM integration for RAG answers and optional image understanding.

Primary provider:
- Cohere command models for text responses
- Cohere vision model for image descriptions

Fallback provider:
- Ollama chat model
- Ollama vision model for image turns when available
"""
import base64
import logging
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional

from django.conf import settings

from .cohere_service import cohere_service

logger = logging.getLogger(__name__)

# Optional Ollama fallback
try:
    from langchain_community.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGCHAIN_OLLAMA_AVAILABLE = True
except ImportError:
    ChatOllama = None
    HumanMessage = None
    SystemMessage = None
    LANGCHAIN_OLLAMA_AVAILABLE = False
    logger.warning("langchain-community not installed for Ollama fallback support")


class MultimodalLLM:
    """
    Multi-provider LLM service.
    Uses Cohere when configured, otherwise falls back to Ollama.
    """

    def __init__(self):
        self.command_model = getattr(settings, 'COHERE_COMMAND_MODEL', 'command-a-03-2025')
        self.vision_model = getattr(settings, 'COHERE_VISION_MODEL', 'command-a-vision-07-2025')
        self.use_cohere = getattr(settings, 'USE_COHERE', True)

        self.ollama_base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
        self.ollama_text_model = getattr(settings, 'OLLAMA_TEXT_MODEL', 'gpt-oss:120b-cloud')
        self.ollama_vision_model = getattr(settings, 'OLLAMA_VISION_MODEL', '').strip()
        self.ollama_vision_fallback_models = list(getattr(
            settings,
            'OLLAMA_VISION_FALLBACK_MODELS',
            [
                'llava:latest',
                'llava:7b',
                'llama3.2-vision:11b',
                'bakllava:latest',
                'qwen2.5vl:7b',
                'gemma3:12b',
                'gemma3:4b',
            ],
        ))
        self._text_llm = None
        self._ollama_available = None
        self._ollama_models = None
        self._resolved_vision_model = None

    @property
    def cohere_enabled(self) -> bool:
        return bool(self.use_cohere and cohere_service.is_available)

    @property
    def text_llm(self):
        """
        LangChain LLM instance.
        Only used for RetrievalQA fallback path.
        """
        if self._text_llm is None and LANGCHAIN_OLLAMA_AVAILABLE:
            try:
                self._text_llm = ChatOllama(
                    model=self.ollama_text_model,
                    base_url=self.ollama_base_url,
                    temperature=0.7,
                )
                logger.info("Initialized fallback Ollama model: %s", self.ollama_text_model)
            except Exception as exc:
                logger.error("Failed to initialize fallback Ollama model: %s", exc)
        return self._text_llm

    def check_ollama_available(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available

        try:
            import requests

            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            self._ollama_available = response.status_code == 200
            if self._ollama_available:
                self._ollama_models = response.json().get('models', [])
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _get_ollama_models(self, force_refresh: bool = False) -> List[Dict]:
        if self._ollama_models is not None and not force_refresh:
            return self._ollama_models
        if not self.check_ollama_available():
            return []
        try:
            import requests

            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            response.raise_for_status()
            self._ollama_models = response.json().get('models', [])
        except Exception as exc:
            logger.warning("Failed to query Ollama model catalog: %s", exc)
            self._ollama_models = []
        return self._ollama_models

    def resolve_vision_model(self, force_refresh: bool = False) -> Optional[str]:
        if self._resolved_vision_model is not None and not force_refresh:
            return self._resolved_vision_model

        models = self._get_ollama_models(force_refresh=force_refresh)
        model_names = [item.get('name') for item in models if item.get('name')]

        if self.ollama_vision_model:
            if self.ollama_vision_model in model_names:
                self._resolved_vision_model = self.ollama_vision_model
                return self._resolved_vision_model
            logger.warning(
                "Configured OLLAMA_VISION_MODEL '%s' is not currently installed. Falling back to auto-detection.",
                self.ollama_vision_model,
            )

        for candidate in self.ollama_vision_fallback_models:
            if candidate in model_names:
                self._resolved_vision_model = candidate
                return self._resolved_vision_model

        for item in models:
            name = (item.get('name') or '').lower()
            details = item.get('details') or {}
            families = [family.lower() for family in (details.get('families') or [])]
            if 'clip' in families or 'vision' in name or 'llava' in name:
                self._resolved_vision_model = item.get('name')
                return self._resolved_vision_model

        self._resolved_vision_model = None
        return None

    def check_ollama_vision_available(self) -> bool:
        return bool(self.resolve_vision_model())

    @staticmethod
    def _compose_messages(prompt: str, system_prompt: str = None) -> List[Dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _encode_image_for_ollama(image_path: str) -> str:
        path = Path(image_path)
        with path.open('rb') as handle:
            return base64.b64encode(handle.read()).decode('utf-8')

    def _compose_vision_messages(
        self,
        prompt: str,
        image_paths: Iterable[str],
        system_prompt: str = None,
        conversation_messages: Optional[Iterable[Dict]] = None,
    ) -> List[Dict]:
        messages: List[Dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for message in conversation_messages or []:
            role = message.get('role')
            content = message.get('content')
            if role in {'user', 'assistant', 'system'} and content:
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": prompt,
                "images": [self._encode_image_for_ollama(path) for path in image_paths],
            }
        )
        return messages

    def generate_vision(
        self,
        prompt: str,
        image_paths: Iterable[str],
        system_prompt: str = None,
        conversation_messages: Optional[Iterable[Dict]] = None,
    ) -> str:
        if not self.check_ollama_available():
            raise RuntimeError("Ollama is not available.")

        model_name = self.resolve_vision_model()
        if not model_name:
            raise RuntimeError("No Ollama vision model is installed.")

        import requests

        response = requests.post(
            f"{self.ollama_base_url}/api/chat",
            json={
                "model": model_name,
                "messages": self._compose_vision_messages(
                    prompt=prompt,
                    image_paths=image_paths,
                    system_prompt=system_prompt,
                    conversation_messages=conversation_messages,
                ),
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        return ((payload.get('message') or {}).get('content') or '').strip()

    def generate_vision_stream(
        self,
        prompt: str,
        image_paths: Iterable[str],
        system_prompt: str = None,
        conversation_messages: Optional[Iterable[Dict]] = None,
    ) -> Generator[str, None, None]:
        if not self.check_ollama_available():
            raise RuntimeError("Ollama is not available.")

        model_name = self.resolve_vision_model()
        if not model_name:
            raise RuntimeError("No Ollama vision model is installed.")

        import json
        import requests

        response = requests.post(
            f"{self.ollama_base_url}/api/chat",
            json={
                "model": model_name,
                "messages": self._compose_vision_messages(
                    prompt=prompt,
                    image_paths=image_paths,
                    system_prompt=system_prompt,
                    conversation_messages=conversation_messages,
                ),
                "stream": True,
                "options": {"temperature": 0.2},
            },
            stream=True,
            timeout=180,
        )
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            chunk = ((data.get('message') or {}).get('content') or '')
            if chunk:
                yield chunk

    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate a full response.
        """
        if self.cohere_enabled:
            try:
                return cohere_service.chat(
                    messages=self._compose_messages(prompt, system_prompt),
                    model=self.command_model,
                )
            except Exception as exc:
                logger.error("Cohere text generation failed, trying fallback: %s", exc)

        if not LANGCHAIN_OLLAMA_AVAILABLE:
            return "No model provider available."
        if not self.check_ollama_available():
            return "No model provider available."

        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            llm = self.text_llm
            if llm is None:
                return "No model provider available."
            response = llm.invoke(messages)
            return response.content
        except Exception as exc:
            logger.error("Fallback generation failed: %s", exc)
            return f"Error: {exc}"

    def generate_stream(self, prompt: str, system_prompt: str = None) -> Generator[str, None, None]:
        """
        Stream response chunks.
        """
        if self.cohere_enabled:
            try:
                for chunk in cohere_service.chat_stream(
                    messages=self._compose_messages(prompt, system_prompt),
                    model=self.command_model,
                ):
                    yield chunk
                return
            except Exception as exc:
                logger.error("Cohere streaming failed, trying fallback: %s", exc)

        if not LANGCHAIN_OLLAMA_AVAILABLE or not self.check_ollama_available():
            yield "No model provider available."
            return

        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            llm = self.text_llm
            if llm is None:
                yield "No model provider available."
                return

            for chunk in llm.stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as exc:
            yield f"Error: {exc}"

    def answer_with_context(self, question: str, text_context: str) -> str:
        """
        Answer a question grounded on retrieved RAG context.
        """
        system_prompt = (
            "You are an expert car mechanic assistant with access to car service manuals. "
            "Use the provided context only. If missing, say you don't have enough context."
        )

        full_prompt = (
            "## Context from uploaded manuals\n"
            f"{text_context}\n\n"
            "## User Question\n"
            f"{question}\n\n"
            "Answer clearly and include safety notes where relevant."
        )
        return self.generate(full_prompt, system_prompt=system_prompt)

    def describe_image(self, image_path: str, question: str = None) -> str:
        """
        Describe and analyze an image with Cohere vision model, then Ollama vision.
        """
        if self.cohere_enabled:
            try:
                return cohere_service.describe_image(image_path, question=question)
            except Exception as exc:
                logger.warning("Cohere image description failed; fallback=ollama-vision: %s", exc)

        try:
            return self.generate_vision(
                prompt=question or "Describe this image accurately.",
                image_paths=[image_path],
            )
        except Exception as exc:
            logger.warning("Ollama vision description failed: %s", exc)
            return "Vision analysis is currently unavailable."

    def get_status(self) -> Dict:
        """
        Return provider and model status.
        """
        return {
            "provider": "cohere" if self.cohere_enabled else "ollama-fallback",
            "cohere_enabled": self.cohere_enabled,
            "cohere_command_model": self.command_model,
            "cohere_vision_model": self.vision_model,
            "ollama_available": self.check_ollama_available(),
            "ollama_url": self.ollama_base_url,
            "ollama_model": self.ollama_text_model,
            "ollama_vision_model": self.resolve_vision_model(),
            "ollama_vision_available": self.check_ollama_vision_available(),
            "fallback_initialized": self._text_llm is not None,
        }


# Global singleton
multimodal_llm = MultimodalLLM()
