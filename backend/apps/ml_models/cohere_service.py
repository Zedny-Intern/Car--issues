"""
Lightweight wrapper around Cohere chat APIs.

Provides:
- command model chat and streaming
- vision model image understanding
- direct multimodal chat helpers for image turns
"""
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import cohere
    COHERE_AVAILABLE = True
except ImportError:
    cohere = None
    COHERE_AVAILABLE = False
    logger.warning("cohere package is not installed")


class CohereService:
    """Cohere chat + vision helper."""
    MAX_EMBED_TEXTS_PER_REQUEST = 96

    def __init__(self):
        self.api_key = getattr(settings, 'COHERE_API_KEY', '')
        self.command_model = getattr(settings, 'COHERE_COMMAND_MODEL', 'command-a-03-2025')
        self.command_fallback_models = list(getattr(
            settings,
            'COHERE_COMMAND_FALLBACK_MODELS',
            ['command-a-03-2025', 'command-r-08-2024', 'command-r7b-12-2024']
        ))
        self.vision_model = getattr(settings, 'COHERE_VISION_MODEL', 'command-a-vision-07-2025')
        self.embed_model = getattr(settings, 'COHERE_EMBED_MODEL', 'embed-v4.0')
        self.embed_input_type_document = getattr(
            settings,
            'COHERE_EMBED_INPUT_TYPE_DOCUMENT',
            'search_document',
        )
        self.embed_input_type_query = getattr(
            settings,
            'COHERE_EMBED_INPUT_TYPE_QUERY',
            'search_query',
        )
        self.embed_output_dimension = int(getattr(settings, 'COHERE_EMBED_OUTPUT_DIMENSION', 512))
        self.temperature = getattr(settings, 'COHERE_TEMPERATURE', 0.3)
        self.max_tokens = getattr(settings, 'COHERE_MAX_TOKENS', 1024)
        self._client = None

    @property
    def is_available(self) -> bool:
        """True when Cohere SDK and API key are configured."""
        return bool(COHERE_AVAILABLE and self.api_key)

    def _get_client(self):
        if not self.is_available:
            return None
        if self._client is None:
            self._client = cohere.ClientV2(api_key=self.api_key)
        return self._client

    @staticmethod
    def _extract_text_from_response(response) -> str:
        """Extract plain text from Cohere chat response object."""
        try:
            content_items = getattr(response.message, 'content', []) or []
            text_parts = []
            for item in content_items:
                item_text = getattr(item, 'text', None)
                if item_text:
                    text_parts.append(item_text)
            if text_parts:
                return "".join(text_parts).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_text_delta(event) -> str:
        """Extract streamed text deltas from Cohere event objects."""
        event_type = getattr(event, 'type', '')
        if event_type != 'content-delta':
            return ""

        delta = getattr(event, 'delta', None)
        if delta is None:
            return ""

        message = getattr(delta, 'message', None)
        if message is None:
            return ""

        content = getattr(message, 'content', None)
        if content is None:
            return ""

        return getattr(content, 'text', '') or ""

    @staticmethod
    def _is_model_not_found_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "status_code: 404" in text
            or "not found" in text
            or "was removed" in text
            or "model '" in text
        )

    @staticmethod
    def summarize_exception(exc: Exception, max_len: int = 360) -> str:
        text = " ".join(str(exc).split())
        if len(text) > max_len:
            return text[:max_len]
        return text

    @staticmethod
    def is_rate_limit_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return (
            "status_code: 429" in text
            or "429 too many requests" in text
            or "too many requests" in text
            or exc.__class__.__name__.lower() == "toomanyrequestserror"
        )

    @staticmethod
    def is_transient_error(exc: Exception) -> bool:
        text = str(exc).lower()
        transient_markers = (
            "timed out",
            "timeout",
            "connection refused",
            "connection reset",
            "temporarily unavailable",
            "service unavailable",
            "bad gateway",
            "status_code: 500",
            "status_code: 502",
            "status_code: 503",
            "status_code: 504",
            "max retries exceeded",
        )
        return any(marker in text for marker in transient_markers)

    @classmethod
    def is_expected_recoverable_error(cls, exc: Exception) -> bool:
        return cls.is_rate_limit_error(exc) or cls.is_transient_error(exc)

    def chat(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        allow_model_fallback: bool = True,
    ) -> str:
        """Synchronous chat request."""
        client = self._get_client()
        if client is None:
            raise RuntimeError("Cohere is not configured")

        selected_model = model or self.command_model
        response = None
        try:
            response = client.chat(
                model=selected_model,
                messages=messages,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as exc:
            if not allow_model_fallback or not self._is_model_not_found_error(exc):
                raise

            for fallback_model in self.command_fallback_models:
                if fallback_model == selected_model:
                    continue
                try:
                    logger.warning(
                        "Cohere model '%s' unavailable. Falling back to '%s'.",
                        selected_model,
                        fallback_model,
                    )
                    response = client.chat(
                        model=fallback_model,
                        messages=messages,
                        temperature=self.temperature if temperature is None else temperature,
                        max_tokens=self.max_tokens if max_tokens is None else max_tokens,
                    )
                    break
                except Exception:
                    continue

            if response is None:
                raise

        text = self._extract_text_from_response(response)
        if text:
            return text
        return "I could not generate a response."

    def chat_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        allow_model_fallback: bool = True,
    ) -> Iterable[str]:
        """Stream text deltas from Cohere chat."""
        client = self._get_client()
        if client is None:
            raise RuntimeError("Cohere is not configured")

        selected_model = model or self.command_model
        stream = None
        try:
            stream = client.chat_stream(
                model=selected_model,
                messages=messages,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as exc:
            if not allow_model_fallback or not self._is_model_not_found_error(exc):
                raise

            for fallback_model in self.command_fallback_models:
                if fallback_model == selected_model:
                    continue
                try:
                    logger.warning(
                        "Cohere streaming model '%s' unavailable. Falling back to '%s'.",
                        selected_model,
                        fallback_model,
                    )
                    stream = client.chat_stream(
                        model=fallback_model,
                        messages=messages,
                        temperature=self.temperature if temperature is None else temperature,
                        max_tokens=self.max_tokens if max_tokens is None else max_tokens,
                    )
                    break
                except Exception:
                    continue

            if stream is None:
                raise

        for event in stream:
            text = self._extract_text_delta(event)
            if text:
                yield text

    @staticmethod
    def _image_to_data_url(image_path: str) -> str:
        """Encode local image as data URL for vision inputs."""
        path = Path(image_path)
        mime_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        with path.open('rb') as f:
            image_bytes = f.read()
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{encoded}"

    def build_multimodal_content(self, prompt_text: str, image_paths: Iterable[str]) -> List[Dict]:
        """Build Cohere multimodal content blocks for the supplied images."""
        content: List[Dict] = [{"type": "text", "text": prompt_text}]
        for image_path in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._image_to_data_url(image_path)},
                }
            )
        return content

    def chat_multimodal(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Chat against the configured vision model without text-model fallback."""
        return self.chat(
            messages=messages,
            model=model or self.vision_model,
            temperature=temperature,
            max_tokens=max_tokens,
            allow_model_fallback=False,
        )

    def chat_stream_multimodal(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterable[str]:
        """Stream responses from the configured vision model without text-model fallback."""
        return self.chat_stream(
            messages=messages,
            model=model or self.vision_model,
            temperature=temperature,
            max_tokens=max_tokens,
            allow_model_fallback=False,
        )

    def describe_image(self, image_path: str, question: Optional[str] = None) -> str:
        """Describe an image with Cohere vision model."""
        if not Path(image_path).exists():
            return "Image not found."

        prompt = question or (
            "Analyze this car image and summarize visible faults, damaged parts, "
            "risk level, and likely mechanical category."
        )
        messages = [
            {
                "role": "user",
                "content": self.build_multimodal_content(prompt, [image_path]),
            }
        ]

        try:
            return self.chat_multimodal(
                messages=messages,
                model=self.vision_model,
                temperature=0.2,
                max_tokens=500,
            )
        except Exception as exc:
            summary = self.summarize_exception(exc)
            if self.is_expected_recoverable_error(exc):
                logger.warning("Cohere vision failed; fallback=legacy-image-summary: %s", summary)
            else:
                logger.error("Cohere vision failed: %s", summary, exc_info=True)
            return f"Image analysis failed: {exc}"

    @staticmethod
    def _extract_float_embeddings(response) -> List[List[float]]:
        embeddings = getattr(response, 'embeddings', None)
        if embeddings is None:
            raise RuntimeError("Cohere embeddings response does not contain embeddings.")

        for attr_name in ('float', 'float_', 'floats'):
            value = getattr(embeddings, attr_name, None)
            if value:
                return value

        if isinstance(embeddings, dict):
            for key in ('float', 'float_', 'floats'):
                value = embeddings.get(key)
                if value:
                    return value

        raise RuntimeError("Could not extract float embeddings from Cohere response.")

    def embed_texts(
        self,
        texts: List[str],
        input_type: str = 'search_document',
        output_dimension: Optional[int] = None,
    ) -> List[List[float]]:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Cohere is not configured")

        normalized_texts = [text for text in texts if text and text.strip()]
        if not normalized_texts:
            return []

        all_embeddings: List[List[float]] = []
        max_batch_size = self.MAX_EMBED_TEXTS_PER_REQUEST

        for start in range(0, len(normalized_texts), max_batch_size):
            batch = normalized_texts[start:start + max_batch_size]
            embed_kwargs = {
                'model': self.embed_model,
                'input_type': input_type,
                'texts': batch,
                'embedding_types': ['float'],
                'output_dimension': output_dimension or self.embed_output_dimension,
            }

            try:
                response = client.embed(**embed_kwargs)
            except TypeError:
                # Older/newer SDK variants may not support one of the optional parameters.
                embed_kwargs.pop('output_dimension', None)
                try:
                    response = client.embed(**embed_kwargs)
                except TypeError:
                    embed_kwargs.pop('embedding_types', None)
                    response = client.embed(**embed_kwargs)

            all_embeddings.extend(self._extract_float_embeddings(response))

        return all_embeddings


# Global singleton
cohere_service = CohereService()
