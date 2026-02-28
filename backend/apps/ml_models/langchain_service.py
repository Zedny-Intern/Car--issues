"""
Mechanic chat service with conversation memory and RAG context.

Primary provider:
- Local-first text chat when configured
- Cohere vision for direct uploaded image understanding

Fallback providers:
- Groq
- Ollama
- OpenAI
"""
import logging
import re
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from django.conf import settings

from .cohere_service import cohere_service
from .multimodal_llm import multimodal_llm
from .rag_agent import multimodal_rag_agent

# Optional provider imports
try:
    from langchain_groq import ChatGroq
    GROQ_AVAILABLE = True
except ImportError:
    ChatGroq = None
    GROQ_AVAILABLE = False

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    ChatOpenAI = None
    OPENAI_AVAILABLE = False

try:
    from langchain.schema import HumanMessage, AIMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    HumanMessage = None
    AIMessage = None
    SystemMessage = None
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


class MechanicChatService:
    """Chat service used by chat session endpoints."""

    def __init__(self):
        self.llm = None
        self.fallback_llm = None
        self.provider = "none"
        self.fallback_provider = "none"
        self.use_cohere = getattr(settings, 'USE_COHERE', True)
        self.command_model = getattr(settings, 'COHERE_COMMAND_MODEL', 'command-a-03-2025')
        self.cohere_vision_model = getattr(settings, 'COHERE_VISION_MODEL', 'command-a-vision-07-2025')
        self.provider_strategy = getattr(settings, 'LLM_PROVIDER_STRATEGY', 'cohere_first').lower()
        if self.provider_strategy not in {'local_first', 'cohere_first'}:
            self.provider_strategy = 'cohere_first'
        self.cohere_image_chat_enabled = bool(getattr(settings, 'COHERE_IMAGE_CHAT_ENABLED', self.use_cohere))
        self.cohere_image_scope = getattr(settings, 'COHERE_IMAGE_SCOPE', 'general').lower()
        self.max_images_per_message = int(getattr(settings, 'COHERE_IMAGE_MAX_IMAGES_PER_MESSAGE', 3))
        self.system_prompt = self._create_system_prompt()
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize provider priority based on configured strategy."""
        if self.provider_strategy == "local_first":
            fallback_provider, fallback_llm = self._ensure_fallback_provider(prefer_local=True)
            if fallback_llm is not None:
                self.provider = fallback_provider
                self.llm = fallback_llm
                logger.info(
                    "Mechanic chat provider initialized with %s (strategy=%s)",
                    fallback_provider,
                    self.provider_strategy,
                )
                return

        if self.use_cohere and cohere_service.is_available:
            self.provider = "cohere"
            logger.info(
                "Mechanic chat provider initialized with Cohere (%s, strategy=%s)",
                self.command_model,
                self.provider_strategy,
            )
            return

        fallback_provider, fallback_llm = self._ensure_fallback_provider(
            prefer_local=self.provider_strategy == "local_first"
        )
        if fallback_llm is not None:
            self.provider = fallback_provider
            self.llm = fallback_llm
            logger.info(
                "Mechanic chat provider initialized with fallback %s (strategy=%s)",
                fallback_provider,
                self.provider_strategy,
            )
            return

        logger.error("No chat provider could be initialized.")

    def _ensure_fallback_provider(self, prefer_local: bool = False):
        """Initialize a non-Cohere provider lazily for runtime failover."""
        if self.fallback_llm is not None and self.fallback_provider != "none":
            return self.fallback_provider, self.fallback_llm

        if not LANGCHAIN_AVAILABLE:
            logger.error("LangChain is not available for fallback providers.")
            return "none", None

        provider_order = ["ollama", "groq", "openai"] if prefer_local else ["groq", "ollama", "openai"]
        for provider_name in provider_order:
            if provider_name == "groq":
                if not (
                    getattr(settings, 'USE_GROQ', False)
                    and getattr(settings, 'GROQ_API_KEY', '')
                    and GROQ_AVAILABLE
                ):
                    continue
                try:
                    self.fallback_llm = ChatGroq(
                        model="qwen/qwen3-32b",
                        temperature=0.6,
                        groq_api_key=settings.GROQ_API_KEY,
                        max_tokens=2048,
                    )
                    self.fallback_provider = "groq"
                    logger.info("Mechanic chat fallback provider initialized with Groq")
                    return self.fallback_provider, self.fallback_llm
                except Exception as exc:
                    logger.warning("Failed to initialize Groq provider: %s", exc)
                    continue

            if provider_name == "ollama":
                try:
                    from langchain_community.chat_models import ChatOllama

                    ollama_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
                    ollama_model = getattr(settings, 'OLLAMA_TEXT_MODEL', 'gpt-oss:120b-cloud')
                    self.fallback_llm = ChatOllama(
                        model=ollama_model,
                        base_url=ollama_url,
                        temperature=0.6,
                    )
                    self.fallback_provider = "ollama"
                    logger.info("Mechanic chat fallback provider initialized with Ollama (%s)", ollama_model)
                    return self.fallback_provider, self.fallback_llm
                except Exception as exc:
                    logger.warning("Failed to initialize Ollama fallback: %s", exc)
                    continue

            if provider_name == "openai":
                if not (getattr(settings, 'OPENAI_API_KEY', '') and OPENAI_AVAILABLE):
                    continue
                try:
                    self.fallback_llm = ChatOpenAI(
                        model="gpt-4",
                        temperature=0.6,
                        openai_api_key=settings.OPENAI_API_KEY,
                    )
                    self.fallback_provider = "openai"
                    logger.info("Mechanic chat fallback provider initialized with OpenAI")
                    return self.fallback_provider, self.fallback_llm
                except Exception as exc:
                    logger.warning("Failed to initialize OpenAI fallback: %s", exc)
                    continue

        return "none", None

    def warm_up(self, preload_rag: bool = True) -> Dict:
        """Eagerly initialize the chat provider and optional RAG dependencies."""
        status = {
            'provider': self.provider,
            'provider_ready': False,
            'rag_ready': False,
            'fallback_provider': None,
        }

        if self.provider == "cohere":
            status['provider_ready'] = bool(cohere_service.is_available)
            fallback_provider, fallback_llm = self._ensure_fallback_provider()
            if fallback_llm is not None:
                status['fallback_provider'] = fallback_provider
        else:
            if self.llm is None and self.provider == "none":
                self._initialize_llm()
            status['provider'] = self.provider
            status['provider_ready'] = self.llm is not None or self.provider == "cohere"

        if preload_rag:
            try:
                rag_status = multimodal_rag_agent.warm_up()
                status['rag_ready'] = bool(rag_status.get('retrieval_chain_ready'))
            except Exception as exc:
                logger.warning("Chat-service RAG warmup failed: %s", exc)

        return status

    @staticmethod
    def _create_system_prompt() -> str:
        return (
            "You are an expert automotive mechanic assistant.\n"
            "Always answer with this structure:\n"
            "1) Understanding the current issue\n"
            "2) Technical analysis linked to this exact vehicle\n"
            "3) Safety assessment (safe/caution/unsafe)\n"
            "4) Action plan with numbered diagnostic and repair steps\n"
            "Answer in the same language as the user's latest message.\n"
            "If complaint-specific uploaded documents exist in the context, acknowledge them by file name.\n"
            "If the user refers to a file generically or with a typo like pdf/bdf/file/document, interpret that as the latest relevant uploaded complaint document unless a different file name is explicitly mentioned.\n"
            "If the user asks what is inside an uploaded file, summarize the uploaded document contents before giving vehicle-diagnosis guidance.\n"
            "If a file is uploaded but still indexing, say that it is uploaded and still being prepared in the background.\n"
            "Never claim that no file was uploaded unless the uploaded-documents section is empty.\n"
            "Do not hallucinate. If data is missing, ask targeted follow-up questions."
        )

    @staticmethod
    def _document_status_label(document_reference: Optional[Dict]) -> str:
        if not document_reference:
            return "unknown"
        if document_reference.get('analysis_error'):
            return f"analysis_error={document_reference['analysis_error']}"
        if document_reference.get('is_analyzed'):
            return "indexed"
        return "pending-analysis"

    @staticmethod
    def _build_document_retrieval_query(user_message: str, document_reference: Optional[Dict]) -> str:
        if not document_reference:
            return user_message
        return (
            f"Uploaded complaint document: {document_reference['file_name']}. "
            f"Summarize its contents and answer this user request about the file: {user_message}"
        )

    @staticmethod
    def _normalize_user_text(value: str) -> str:
        return re.sub(r'[^0-9A-Za-z\u0600-\u06FF]+', ' ', (value or '').lower()).strip()

    @classmethod
    def _is_uploaded_document_content_request(
        cls,
        user_message: str,
        document_reference: Optional[Dict],
    ) -> bool:
        if not document_reference:
            return False

        normalized = cls._normalize_user_text(user_message)
        tokens = {
            token for token in normalized.split()
            if len(token) > 1
        }
        content_terms = {
            'content', 'contents', 'inside', 'summary', 'summarize', 'review',
            'read', 'explain', 'tell', 'what',
            'محتوى', 'محتوي', 'ملخص', 'الموجود', 'داخل', 'جوه', 'فيه',
            'اقرا', 'اقرأ', 'راجع', 'ايه', 'إيه',
        }
        document_fragments = (
            'pdf', 'bdf', 'file', 'document', 'report',
            'ملف', 'فايل', 'مستند', 'وثيقة', 'مرفق', 'تقرير',
        )
        refers_to_document = any(fragment in normalized for fragment in document_fragments)
        asks_for_contents = bool(tokens & content_terms) or ('?' in (user_message or '')) or ('؟' in (user_message or ''))
        return refers_to_document and asks_for_contents

    @staticmethod
    def _contains_arabic(text: str) -> bool:
        return bool(re.search(r'[\u0600-\u06FF]', text or ''))

    def _detect_response_language(
        self,
        chat_session=None,
        user_message: str = "",
        fallback_text: str = "",
    ) -> str:
        candidates: List[str] = [user_message, fallback_text]

        if chat_session is not None:
            complaint_text = getattr(getattr(chat_session, 'complaint', None), 'complaint_text', '')
            if complaint_text:
                candidates.append(complaint_text)
            try:
                for msg in reversed(chat_session.get_messages_for_context(limit=6)):
                    if msg.get('role') != 'assistant' and msg.get('content'):
                        candidates.append(msg['content'])
                        break
            except Exception:
                pass

        for candidate in candidates:
            if self._contains_arabic(candidate):
                return "arabic"
        return "english"

    def _build_language_instruction(
        self,
        chat_session=None,
        user_message: str = "",
        fallback_text: str = "",
    ) -> str:
        language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=fallback_text,
        )
        if language == "arabic":
            return (
                "The user's active language is Arabic. You must answer fully in Arabic. "
                "Do not switch to English except for exact file names, URLs, brand/model names, "
                "diagnostic codes, or literal API/provider names. Keep the headings and explanation in Arabic.\n"
                "أجب بالعربية فقط. اجعل العناوين والشرح بالعربية، ولا تستخدم الإنجليزية إلا عند الحاجة للاسم الحرفي أو الكود."
            )
        return (
            "The user's active language is English. You must answer fully in English. "
            "Do not switch to Arabic unless the user explicitly asks for Arabic."
        )

    @staticmethod
    def _script_counts(text: str) -> Dict[str, int]:
        value = text or ""
        return {
            "arabic": len(re.findall(r'[\u0600-\u06FF]', value)),
            "latin": len(re.findall(r'[A-Za-z]', value)),
        }

    def _response_matches_language(self, response_text: str, target_language: str) -> bool:
        counts = self._script_counts(response_text)
        if target_language == "arabic":
            return counts["arabic"] > 0 and counts["arabic"] >= counts["latin"]
        return counts["latin"] > 0

    def _rewrite_response_in_target_language(
        self,
        chat_session,
        user_message: str,
        response_text: str,
    ) -> Optional[str]:
        target_language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        if self._response_matches_language(response_text, target_language):
            return response_text

        provider_name, llm = self._ensure_fallback_provider(prefer_local=True)
        if llm is None:
            return None

        if target_language == "arabic":
            rewrite_instruction = (
                "أعد كتابة الرد التالي بالعربية فقط مع الحفاظ على نفس المعنى ونفس الهيكل. "
                "لا تضف معلومات جديدة، ولا تحذف حقائق موجودة. اترك أسماء الملفات والروابط "
                "وأسماء الموديلات والأكواد كما هي حرفيًا إذا لزم الأمر."
            )
        else:
            rewrite_instruction = (
                "Rewrite the following answer fully in English while preserving the same meaning and structure. "
                "Do not add new facts and do not remove existing facts. Keep file names, URLs, model names, "
                "and codes exactly as they are when needed."
            )

        try:
            messages = [
                SystemMessage(content=rewrite_instruction),
                HumanMessage(content=response_text),
            ]
            rewritten = llm.invoke(messages)
            content = getattr(rewritten, 'content', rewritten)
            if not content:
                return None
            rewritten_text = str(content).strip()
            if self._response_matches_language(rewritten_text, target_language):
                logger.info(
                    "Rewrote assistant response to align with target language via %s",
                    provider_name,
                )
                return rewritten_text
        except Exception as exc:
            self._log_provider_failure(
                provider=provider_name,
                operation="language-rewrite",
                exc=exc,
                fallback_target="original-response",
            )
        return None

    def _ensure_response_language(
        self,
        chat_session,
        user_message: str,
        response_text: Optional[str],
    ) -> Optional[str]:
        if not response_text:
            return response_text
        target_language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        if self._response_matches_language(response_text, target_language):
            return response_text
        rewritten = self._rewrite_response_in_target_language(
            chat_session=chat_session,
            user_message=user_message,
            response_text=response_text,
        )
        return rewritten or response_text

    @staticmethod
    def _stream_text_chunks(text: str, chunk_size: int = 220):
        if not text:
            return
        normalized_text = text.replace('\r\n', '\n')
        for paragraph in normalized_text.split('\n\n'):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) <= chunk_size:
                yield paragraph + "\n\n"
                continue
            start = 0
            while start < len(paragraph):
                end = min(start + chunk_size, len(paragraph))
                yield paragraph[start:end]
                start = end
            yield "\n\n"

    def _build_uploaded_document_summary_response(
        self,
        chat_session,
        user_message: str,
        rag_context: str = "",
    ) -> Optional[str]:
        document_reference = chat_session.resolve_uploaded_document_reference(reference_query=user_message)
        if not self._is_uploaded_document_content_request(user_message, document_reference):
            return None

        full_context = chat_session.build_full_context_for_llm(reference_query=user_message)
        uploaded_documents = full_context.get('uploaded_documents', [])
        document_context = next(
            (document for document in uploaded_documents if document['id'] == document_reference['id']),
            None,
        )
        is_arabic = self._contains_arabic(user_message)
        status_label = self._document_status_label(document_reference)

        if not document_context:
            if is_arabic:
                return (
                    "1) الملف المقصود\n"
                    f"- أقرب ملف مقصود في هذه الجلسة هو `{document_reference['file_name']}`.\n\n"
                    "2) حالة الملف\n"
                    "- الملف مرفوع، لكن لم أستطع تحميل سياقه التفصيلي داخل هذه اللحظة.\n\n"
                    "3) علاقته بالشكوى الحالية\n"
                    "- أحتاج إعادة قراءة الفهرسة الخاصة به قبل أن ألخص مضمونه بدقة.\n\n"
                    "4) الخطوة التالية\n"
                    "1. اسألني مرة أخرى بعد ثوانٍ قليلة.\n"
                    "2. إذا استمرت المشكلة، أعد رفع الملف على نفس الشكوى."
                )
            return (
                "1) File reference\n"
                f"- The most likely file you mean is `{document_reference['file_name']}`.\n\n"
                "2) File status\n"
                "- The file is uploaded, but its detailed context could not be loaded right now.\n\n"
                "3) Relevance\n"
                "- I need the indexing context to summarize it accurately.\n\n"
                "4) Next step\n"
                "1. Ask again in a few seconds.\n"
                "2. Re-upload the file to the same complaint if the issue persists."
            )

        excerpts = document_context.get('excerpts', [])
        excerpt_lines = [excerpt['text'] for excerpt in excerpts if excerpt.get('text')]
        primary_excerpt = excerpt_lines[0] if excerpt_lines else ""
        secondary_excerpt = excerpt_lines[1] if len(excerpt_lines) > 1 else ""
        rag_hint = self._clean_provider_text(rag_context, max_len=500)

        if is_arabic:
            if document_reference.get('analysis_error'):
                return (
                    "1) الملف المقصود\n"
                    f"- الملف الذي تقصده هو `{document_reference['file_name']}`.\n\n"
                    "2) حالة الملف\n"
                    f"- تم رفع الملف، لكن الفهرسة فشلت حاليًا: {document_reference['analysis_error']}\n\n"
                    "3) المحتوى المتاح الآن\n"
                    "- لا يوجد نص مفهرس موثوق يمكن تلخيصه حاليًا من هذا الملف.\n\n"
                    "4) الخطوة التالية\n"
                    "1. أعد رفع الملف أو شغّل إعادة الفهرسة.\n"
                    "2. بعد نجاح الفهرسة سأقدر ألخصه لك مباشرة."
                )
            if not document_reference.get('is_analyzed'):
                return (
                    "1) الملف المقصود\n"
                    f"- الملف الذي تقصده هو `{document_reference['file_name']}`.\n\n"
                    "2) حالة الملف\n"
                    f"- الملف مرفوع، لكن حالته الآن `{status_label}` وما زالت الفهرسة تعمل في الخلفية.\n\n"
                    "3) المحتوى المتاح الآن\n"
                    "- لا أملك بعد ملخصًا كاملًا من داخل الملف، لكن بمجرد اكتمال الفهرسة سأقدر أقرأه وألخصه.\n\n"
                    "4) الخطوة التالية\n"
                    "1. انتظر قليلًا ثم اسألني مرة أخرى عن محتوى الملف.\n"
                    "2. إذا أردت، أقدر أؤكد لك فقط اسم الملف ونوعه وحالة فهرسته الآن."
                )

            content_lines = [
                "1) الملف المقصود",
                f"- أنت غالبًا تقصد الملف المرفوع `{document_reference['file_name']}`.",
                f"- حالة الملف الآن: `{status_label}`، وعدد الصفحات المفهرسة تقريبًا {document_context.get('page_count') or 'غير معروف'}.",
                "",
                "2) ماذا يوجد داخل الملف",
            ]
            if primary_excerpt:
                content_lines.append(
                    f"- بداية الملف تشير إلى أنه تقرير/مشروع بعنوان قريب من: {primary_excerpt}"
                )
            if secondary_excerpt:
                content_lines.append(
                    f"- كما يظهر من النص المفهرس أيضًا: {secondary_excerpt}"
                )
            if rag_hint:
                content_lines.append(f"- من السياق المفهرس الإضافي: {rag_hint}")
            if not excerpt_lines and not rag_hint:
                content_lines.append("- الملف مفهرس، لكن لم أستخرج منه مقتطفًا واضحًا في هذه اللحظة.")

            content_lines.extend([
                "",
                "3) علاقته بالشكوى الحالية",
                "- هذا الملف يبدو أقرب إلى تقرير/محتوى أكاديمي أو عام، وليس تقرير تشخيص سيارة مباشرًا.",
                "- لو كنت تقصد ملفًا آخر خاصًا بالعطل أو تقرير فحص للسيارة، فالملف الحالي ليس هو المستند المناسب للتحليل الميكانيكي.",
                "",
                "4) الخطوة التالية",
                "1. إذا أردت، أقدر ألخص لك الملف كاملًا أو أستخرج أهم النقاط منه.",
                "2. إذا كنت تقصد PDF آخر خاص بالسيارة، ارفعه على نفس الشكوى وسأقرأه مباشرة.",
            ])
            return "\n".join(content_lines)

        content_lines = [
            "1) File reference",
            f"- You most likely mean the uploaded file `{document_reference['file_name']}`.",
            f"- Current status: `{status_label}` with about {document_context.get('page_count') or 'unknown'} indexed pages.",
            "",
            "2) What is inside the file",
        ]
        if primary_excerpt:
            content_lines.append(f"- The beginning of the file indicates content like: {primary_excerpt}")
        if secondary_excerpt:
            content_lines.append(f"- Another indexed excerpt says: {secondary_excerpt}")
        if rag_hint:
            content_lines.append(f"- Additional indexed context: {rag_hint}")
        if not excerpt_lines and not rag_hint:
            content_lines.append("- The file is indexed, but no clear excerpt was available at this moment.")

        content_lines.extend([
            "",
            "3) Relevance to this complaint",
            "- This looks more like a general or academic report than a direct vehicle diagnostic report.",
            "- If you meant a different car-related PDF, the currently linked file is probably not the one you intended to analyze.",
            "",
            "4) Next step",
            "1. I can summarize this PDF in more detail if you want.",
            "2. If you meant another vehicle document, upload it to the same complaint and I will read that one instead.",
        ])
        return "\n".join(content_lines)

    def _build_context_message(self, chat_session, reference_query: Optional[str] = None) -> str:
        """Create vehicle + complaint context."""
        context = chat_session.build_full_context_for_llm(reference_query=reference_query)
        vehicle = context['vehicle']
        current = context['current_complaint']
        history = context['historical_complaints']
        recurring = context['recurring_issues']
        uploaded_documents = context.get('uploaded_documents', [])
        resolved_document = chat_session.resolve_uploaded_document_reference(reference_query=reference_query)

        parts = [
            "VEHICLE",
            f"- Vehicle: {vehicle['display_name']}",
            f"- License Plate: {vehicle['license_plate']}",
            f"- Mileage: {vehicle['mileage']:,} km",
            f"- Total complaints: {vehicle['total_complaints']}",
            "",
            "CURRENT COMPLAINT",
            f"- Category: {current['category']}",
            f"- Confidence: {current['confidence']:.1%}",
            f"- Status: {current['status']}",
            f"- Created at: {current['created_at']}",
            f"- Crash involved: {current['crash']}",
            f"- Fire involved: {current['fire']}",
            "",
            f"Customer description:\n{current['text']}",
        ]

        if recurring:
            parts.append("\nRECURRING ISSUES")
            for issue in recurring:
                parts.append(
                    f"- {issue['category']}: {issue['count']} times "
                    f"(first {issue['first_occurrence'].strftime('%Y-%m-%d')}, "
                    f"last {issue['last_occurrence'].strftime('%Y-%m-%d')})"
                )

        parts.append("\nHISTORICAL COMPLAINTS")
        if history:
            for item in history:
                parts.append(
                    f"- [{item['date']}] {item['category']} | crash={item['crash']} | fire={item['fire']} "
                    f"| {item['text']}"
                )
        else:
            parts.append("- No previous complaints.")

        parts.append("\nUPLOADED COMPLAINT DOCUMENTS")
        if uploaded_documents:
            for document in uploaded_documents:
                uploaded_at = (
                    document['uploaded_at'].strftime('%Y-%m-%d %H:%M')
                    if getattr(document.get('uploaded_at'), 'strftime', None)
                    else str(document.get('uploaded_at'))
                )
                status_parts = []
                if document.get('is_indexed'):
                    status_parts.append("indexed")
                elif document.get('is_analyzed'):
                    status_parts.append("uploaded")
                else:
                    status_parts.append("pending-analysis")
                if document.get('analysis_error'):
                    status_parts.append(f"analysis_error={document['analysis_error']}")
                if document.get('index_error'):
                    status_parts.append(f"index_error={document['index_error']}")

                parts.append(
                    f"- File: {document['file_name']} ({document['file_type']}) | uploaded {uploaded_at} | "
                    f"status: {', '.join(status_parts)}"
                )
                if document.get('is_latest_upload'):
                    parts.append("  This is the latest uploaded complaint document.")
                if document.get('page_count'):
                    parts.append(
                        f"  Indexed pages: {document['page_count']} | chunks: {document.get('chunk_count', 0)}"
                    )
                for excerpt in document.get('excerpts', []):
                    parts.append(
                        f"  Excerpt (page {excerpt['page']}, {excerpt['chunk_type']}): {excerpt['text']}"
                    )
        else:
            parts.append("- No complaint-specific uploaded documents are attached to this complaint.")

        parts.append("\nTURN-SPECIFIC DOCUMENT REFERENCE")
        if resolved_document:
            if resolved_document.get('match_reason') == 'filename-match':
                reason_text = "the user query matched this file name directly"
            else:
                reason_text = "the user referred to a generic/misspelled file term, so this latest upload should be treated as the intended file"
            parts.append(
                f"- Treat this turn as referring to: {resolved_document['file_name']} ({resolved_document['file_type']}) "
                f"| status: {self._document_status_label(resolved_document)}"
            )
            parts.append(f"- Resolution reason: {reason_text}")
            if not resolved_document.get('is_analyzed'):
                parts.append("- The file exists, but its full indexing/analysis is still running in the background.")
        else:
            parts.append("- No single uploaded file reference was resolved for this turn.")

        return "\n".join(parts)

    @staticmethod
    def _append_extra_context(base_context: str, extra_context: Optional[str]) -> str:
        if not extra_context:
            return base_context
        return f"{base_context}\n\nADDITIONAL CONTEXT\n{extra_context}"

    def _build_cohere_messages(
        self,
        chat_session,
        user_message: str,
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None
    ) -> List[Dict]:
        context_text = self._append_extra_context(
            self._build_context_message(chat_session, reference_query=user_message),
            extra_context
        )
        language_instruction = self._build_language_instruction(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        messages: List[Dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": language_instruction},
            {"role": "system", "content": context_text},
        ]

        if use_conversation_memory:
            for msg in chat_session.get_messages_for_context(limit=15):
                role = "assistant" if msg['role'] == 'assistant' else "user"
                messages.append({"role": role, "content": msg['content']})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _build_langchain_messages(
        self,
        chat_session,
        user_message: str,
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None
    ):
        context_text = self._append_extra_context(
            self._build_context_message(chat_session, reference_query=user_message),
            extra_context
        )
        language_instruction = self._build_language_instruction(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        messages = [
            SystemMessage(content=self.system_prompt),
            SystemMessage(content=language_instruction),
            SystemMessage(content=context_text),
        ]

        if use_conversation_memory:
            for msg in chat_session.get_messages_for_context(limit=15):
                if msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))
                else:
                    messages.append(HumanMessage(content=msg['content']))

        messages.append(HumanMessage(content=user_message))
        return messages

    @staticmethod
    def _collect_rag_context(chat_session, user_message: str, top_k: int = 3) -> str:
        """Retrieve relevant chunks from uploaded documents."""
        timeout_seconds = float(getattr(settings, 'RAG_RETRIEVAL_TIMEOUT_SECONDS', 20))
        result_holder = {"result": None, "error": None}
        done_event = threading.Event()
        preferred_source_paths = []
        resolved_document = None
        retrieval_query = user_message

        if chat_session is not None:
            try:
                resolved_document = chat_session.resolve_uploaded_document_reference(reference_query=user_message)
                preferred_source_paths = chat_session.get_uploaded_document_paths()
                if resolved_document and resolved_document.get('file_path'):
                    preferred_source_paths = [resolved_document['file_path']] + [
                        path for path in preferred_source_paths
                        if path != resolved_document['file_path']
                    ]
                    retrieval_query = MechanicChatService._build_document_retrieval_query(
                        user_message=user_message,
                        document_reference=resolved_document,
                    )
            except Exception as exc:
                logger.warning("Could not collect preferred uploaded-document paths: %s", exc)

        def run_retrieval():
            try:
                result_holder["result"] = multimodal_rag_agent.retrieve(
                    query=retrieval_query,
                    top_k=top_k,
                    preferred_source_paths=preferred_source_paths,
                )
            except Exception as exc:
                result_holder["error"] = exc
            finally:
                done_event.set()

        try:
            worker = threading.Thread(target=run_retrieval, daemon=True)
            worker.start()
            if not done_event.wait(timeout_seconds):
                logger.warning(
                    "RAG retrieval timed out after %.1fs. Continuing without RAG context.",
                    timeout_seconds,
                )
                return ""
            if result_holder["error"] is not None:
                raise result_holder["error"]
            result = result_holder["result"] or {}
            return result.get("context") or ""
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            return ""

    def _analyze_images(self, image_paths: Optional[Iterable[str]], user_message: str) -> str:
        """Analyze uploaded images using Cohere vision and return textual summary."""
        if not image_paths:
            return ""
        if not (self.use_cohere and cohere_service.is_available):
            return ""

        analyses = []
        for index, path in enumerate(image_paths, start=1):
            prompt = (
                "Analyze this car image for visible mechanical or body issues. "
                f"User message: {user_message}"
            )
            summary = cohere_service.describe_image(path, question=prompt)
            if not summary or summary.lower().startswith("image analysis failed"):
                logger.warning("Skipping image analysis for %s because the vision provider is unavailable.", path)
                continue
            analyses.append(f"[Image {index} - {Path(path).name}] {summary}")

        return "\n".join(analyses)

    @staticmethod
    def _clean_provider_text(text: Optional[str], max_len: int = 700) -> str:
        normalized = " ".join((text or "").replace("\x00", " ").split())
        if max_len and len(normalized) > max_len:
            return normalized[:max_len]
        return normalized

    def _normalize_image_paths(self, image_paths: Optional[Iterable[str]]) -> List[str]:
        normalized: List[str] = []
        for raw_path in image_paths or []:
            if not raw_path:
                continue
            path = Path(str(raw_path))
            if not path.exists():
                logger.warning("Skipping missing chat image path: %s", path)
                continue
            normalized.append(str(path))

        if len(normalized) > self.max_images_per_message:
            logger.warning(
                "Received %s chat images; truncating to first %s for Cohere Vision.",
                len(normalized),
                self.max_images_per_message,
            )
        return normalized[:self.max_images_per_message]

    @staticmethod
    def _has_meaningful_user_text(user_message: str) -> bool:
        normalized = " ".join((user_message or "").strip().lower().split())
        default_image_prompts = {
            "",
            "please analyze the uploaded image(s) and explain the issue.",
            "please analyze the uploaded image(s) and explain the issue",
        }
        return normalized not in default_image_prompts

    def _should_use_cohere_vision(self, image_paths: Optional[Iterable[str]]) -> bool:
        return bool(
            image_paths
            and self.cohere_image_chat_enabled
            and self.use_cohere
            and cohere_service.is_available
        )

    def _build_vision_prompt(self, chat_session, user_message: str) -> str:
        scope_map = {
            'general': (
                "Analyze any image accurately. If it is vehicle-related, provide a deeper "
                "automotive diagnosis. If not, describe it clearly without forcing a car diagnosis."
            ),
            'car_only': (
                "Prioritize vehicle and vehicle-component analysis. If the image is not automotive, "
                "state clearly that it is outside the intended mechanic scope."
            ),
            'mixed_auto_bias': (
                "Analyze any image, but when a vehicle or vehicle part is visible, switch into "
                "mechanic-diagnostic mode with stronger automotive detail."
            ),
        }
        if self._has_meaningful_user_text(user_message):
            user_request = self._clean_provider_text(user_message, max_len=600)
        else:
            user_request = (
                "The user attached image(s) without a detailed text description. "
                "Infer only what is visually supported and explicitly ask for another angle if needed."
            )
        language_instruction = self._build_language_instruction(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        if language == "arabic":
            return (
                "حلل الصورة أو الصور المرفقة مباشرة، ولا تقل إنه لم يتم إرسال صورة.\n"
                f"{language_instruction}\n"
                "ابدأ أولًا بتحديد ما إذا كانت الصورة مرتبطة بسيارة أو جزء منها.\n"
                "صف فقط التفاصيل التي تظهر فعلًا في الصورة. استخدم سياق الشكوى وتاريخ السيارة كخلفية مساعدة فقط، "
                "وليس كدليل على ما يظهر بصريًا.\n"
                "إذا كانت الصورة لسيارة أو جزء منها، فاشرح العطل أو الضرر الظاهر، والنظام المتأثر غالبًا، "
                "ومستوى الخطورة الفوري، ثم الخطوة التشخيصية التالية.\n"
                "إذا كانت الصورة غير مرتبطة بالسيارات، فصف ما يظهر بوضوح واذكر أن الربط الميكانيكي غير مؤكد أو غير مناسب.\n"
                "إذا كانت الصورة ضبابية أو ناقصة أو غير حاسمة، فاطلب زاوية أو صورة أوضح.\n"
                "التزم بهذا الهيكل:\n"
                "1) فهم المشكلة الحالية\n"
                "2) التحليل الفني المرتبط بهذه السيارة أو بهذه الصورة\n"
                "3) تقييم السلامة (آمن/حذر/غير آمن أو غير منطبق)\n"
                "4) خطة العمل والخطوات التالية\n"
                f"وضع نطاق تحليل الصور: {scope_map.get(self.cohere_image_scope, scope_map['general'])}\n"
                f"آخر طلب من المستخدم: {user_request}"
            )

        return (
            "Analyze the attached image(s) directly. Do not say that no image was provided.\n"
            f"{language_instruction}\n"
            "First determine whether the image is automotive-related.\n"
            "Only describe visual details that are actually visible in the image(s). "
            "Use complaint history and vehicle context only as supporting background, not as proof of what is visible.\n"
            "If it shows a vehicle or a vehicle component, explain visible faults or damage, the likely "
            "affected system, the immediate risk level, and the next diagnostic step.\n"
            "If it is not automotive-related, describe what is visible clearly and say that the automotive "
            "link is uncertain or not applicable.\n"
            "If the image is blurry, cropped, or inconclusive, ask for a clearer angle or additional image.\n"
            "Keep this structure:\n"
            "1) Understanding the current issue\n"
            "2) Technical analysis linked to this exact vehicle or image\n"
            "3) Safety assessment (safe/caution/unsafe or not applicable)\n"
            "4) Action plan with numbered next steps\n"
            f"Image scope mode: {scope_map.get(self.cohere_image_scope, scope_map['general'])}\n"
            f"Latest user request: {user_request}"
        )

    def _build_multimodal_cohere_messages(
        self,
        chat_session,
        user_message: str,
        image_paths: Iterable[str],
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None,
    ) -> List[Dict]:
        context_text = self._append_extra_context(
            self._build_context_message(chat_session, reference_query=user_message),
            extra_context,
        )
        language_instruction = self._build_language_instruction(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        messages: List[Dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": language_instruction},
            {"role": "system", "content": context_text},
        ]

        if use_conversation_memory:
            for msg in chat_session.get_messages_for_context(limit=15):
                role = "assistant" if msg['role'] == 'assistant' else "user"
                messages.append({"role": role, "content": msg['content']})

        messages.append(
            {
                "role": "user",
                "content": cohere_service.build_multimodal_content(
                    self._build_vision_prompt(chat_session, user_message),
                    image_paths,
                ),
            }
        )
        return messages

    def _build_multimodal_ollama_context(
        self,
        chat_session,
        user_message: str,
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None,
    ):
        context_text = self._append_extra_context(
            self._build_context_message(chat_session, reference_query=user_message),
            extra_context,
        )
        language_instruction = self._build_language_instruction(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=getattr(chat_session.complaint, 'complaint_text', ''),
        )
        if language == "arabic":
            language_instruction = (
                f"{language_instruction}\n"
                "أعطِ الرد النهائي بالعربية حتى لو كانت بعض بيانات السياق أو المرفقات تحتوي نصًا إنجليزيًا."
            )
        system_prompt = f"{self.system_prompt}\n\n{language_instruction}\n\n{context_text}"
        conversation_messages: List[Dict] = []
        if use_conversation_memory:
            for msg in chat_session.get_messages_for_context(limit=15):
                role = "assistant" if msg['role'] == 'assistant' else "user"
                conversation_messages.append({"role": role, "content": msg['content']})
        return system_prompt, conversation_messages

    def _generate_with_local_vision_provider(
        self,
        chat_session,
        user_message: str,
        image_paths: Iterable[str],
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None,
    ) -> Optional[str]:
        if not multimodal_llm.check_ollama_vision_available():
            return None
        try:
            system_prompt, conversation_messages = self._build_multimodal_ollama_context(
                chat_session=chat_session,
                user_message=user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=extra_context,
            )
            return multimodal_llm.generate_vision(
                prompt=self._build_vision_prompt(chat_session, user_message),
                image_paths=image_paths,
                system_prompt=system_prompt,
                conversation_messages=conversation_messages,
            )
        except Exception as exc:
            self._log_provider_failure(
                provider="ollama",
                operation="vision-chat",
                exc=exc,
                fallback_target="local-text",
            )
            return None

    def _stream_with_local_vision_provider(
        self,
        chat_session,
        user_message: str,
        image_paths: Iterable[str],
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None,
    ):
        if not multimodal_llm.check_ollama_vision_available():
            return None
        try:
            system_prompt, conversation_messages = self._build_multimodal_ollama_context(
                chat_session=chat_session,
                user_message=user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=extra_context,
            )
            return multimodal_llm.generate_vision_stream(
                prompt=self._build_vision_prompt(chat_session, user_message),
                image_paths=image_paths,
                system_prompt=system_prompt,
                conversation_messages=conversation_messages,
            )
        except Exception as exc:
            self._log_provider_failure(
                provider="ollama",
                operation="vision-stream",
                exc=exc,
                fallback_target="local-text",
            )
            return None

    @staticmethod
    def _classify_provider_reason(reason) -> str:
        lowered = str(reason).lower()
        if "429" in lowered or "too many requests" in lowered:
            return "rate_limit"
        if any(
            marker in lowered for marker in (
                "connection refused",
                "temporarily unavailable",
                "timed out",
                "timeout",
                "service unavailable",
                "bad gateway",
                "max retries exceeded",
            )
        ):
            return "temporary_provider_error"
        return "unexpected_provider_error"

    def _build_image_fallback_notice(self, user_message: str, reason: str) -> str:
        reason_key = self._classify_provider_reason(reason)
        if self._contains_arabic(user_message):
            reason_map = {
                "rate_limit": "لأن مزود الرؤية وصل إلى حد الطلبات",
                "temporary_provider_error": "لأن مزود الرؤية غير متاح مؤقتًا",
                "unexpected_provider_error": "بسبب مشكلة مؤقتة في مزود الرؤية",
            }
            return (
                f"تعذر تحليل الصورة مباشرة الآن {reason_map.get(reason_key, reason_map['unexpected_provider_error'])}، "
                "لذلك سأعتمد على وصفك النصي وسياق الشكوى فقط."
            )
        reason_map = {
            "rate_limit": "because the vision provider hit its rate limit",
            "temporary_provider_error": "because the vision provider is temporarily unavailable",
            "unexpected_provider_error": "because the vision provider failed unexpectedly",
        }
        return (
            f"Direct image analysis is temporarily unavailable {reason_map.get(reason_key, reason_map['unexpected_provider_error'])}, "
            "so I will rely only on your text description and the complaint context."
        )

    def _build_image_fallback_user_message(self, user_message: str) -> str:
        if not self._has_meaningful_user_text(user_message):
            return ""
        if self._contains_arabic(user_message):
            unavailable_note = (
                "مهم: تحليل الصورة المرفقة غير متاح الآن بشكل مباشر. "
                "لا تدّع أنك ترى الصورة. ابنِ الرد فقط على وصف المستخدم النصي "
                "وسياق الشكوى وأي سياق موثوق تم استرجاعه."
            )
        else:
            unavailable_note = (
                "IMPORTANT: Direct analysis of the attached image(s) is currently unavailable. "
                "Do not claim that you can see the image. Base the answer only on the user's text "
                "description, complaint context, and any retrieved manual context."
            )
        return (
            f"{user_message}\n\n"
            f"{unavailable_note}"
        )

    def _build_image_fallback_response(
        self,
        chat_session,
        user_message: str,
        image_paths: Optional[Iterable[str]],
        reason: str,
    ) -> str:
        if self._has_meaningful_user_text(user_message):
            base_response = self._build_local_fallback_response(
                chat_session=chat_session,
                user_message=user_message,
                rag_context="",
            )
            return f"{self._build_image_fallback_notice(user_message, reason)}\n\n{base_response}"

        complaint = chat_session.complaint
        vehicle_name = chat_session.car.display_name
        safety_level, safety_note = self._assess_safety(chat_session)
        image_count = len(list(image_paths or []))
        reason_key = self._classify_provider_reason(reason)
        reason_labels = {
            "rate_limit": "vision provider rate limit",
            "temporary_provider_error": "temporary vision-provider outage",
            "unexpected_provider_error": "vision-provider failure",
        }
        summarized_reason = reason_labels.get(reason_key, reason_labels["unexpected_provider_error"])

        if self._contains_arabic(user_message or complaint.complaint_text):
            return "\n".join([
                "1) فهم الحالة الحالية",
                f"- استلمت {image_count} صورة لكن تعذر تحليلها مباشرة الآن ({summarized_reason}).",
                f"- لا يوجد وصف نصي كافٍ يشرح ما الذي أبحث عنه في صور {vehicle_name}.",
                "",
                "2) التحليل الفني المرتبط بهذه المركبة أو الصورة",
                "- لن أفترض محتوى الصورة بصريًا بدون تحليل مباشر موثوق.",
                "- أحتاج وصفًا مختصرًا لما يظهر في الصورة أو زاوية أوضح قبل إعطاء تشخيص مرئي.",
                "",
                "3) تقييم السلامة",
                f"- {safety_level.upper()}: {safety_note}",
                "",
                "4) خطة العمل",
                "1. أعد رفع الصورة أو أرسل لقطة أوضح للجزء المطلوب.",
                "2. اكتب سطرًا واحدًا يوضح ما الذي تريد تحليله في الصورة.",
                "3. إذا كانت الصورة لجزء من السيارة، اذكر مكانه والأعراض المرتبطة به.",
            ])

        return "\n".join([
            "1) Understanding the current issue",
            f"- I received {image_count} image(s), but direct image analysis is unavailable right now ({summarized_reason}).",
            f"- There is not enough text to determine what I should inspect in the image for {vehicle_name}.",
            "",
            "2) Technical analysis linked to this exact vehicle or image",
            "- I will not guess what is visible without a reliable direct image analysis path.",
            "- Please add a short text description or a clearer angle so I can give a grounded answer.",
            "",
            "3) Safety assessment",
            f"- {safety_level.upper()}: {safety_note}",
            "",
            "4) Action plan",
            "1. Re-upload the image or send a clearer angle of the relevant part.",
            "2. Add one short sentence describing what you want inspected in the image.",
            "3. If the image shows a vehicle part, mention where it is located and the symptom you noticed.",
        ])

    @staticmethod
    def _is_expected_provider_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return cohere_service.is_expected_recoverable_error(exc) or any(
            marker in text for marker in (
                "connection refused",
                "temporarily unavailable",
                "timed out",
                "timeout",
                "max retries exceeded",
                "failed to establish a new connection",
            )
        )

    def _log_provider_failure(
        self,
        provider: str,
        operation: str,
        exc: Exception,
        fallback_target: Optional[str] = None,
    ) -> None:
        summary = cohere_service.summarize_exception(exc)
        message = f"{provider} {operation} failed"
        if fallback_target:
            message += f"; fallback={fallback_target}"
        message += f": {summary}"
        if self._is_expected_provider_error(exc):
            logger.warning(message)
        else:
            logger.error(message, exc_info=True)

    @staticmethod
    def _assess_safety(chat_session):
        complaint = chat_session.complaint
        critical_category_ids = {
            'advanced_safety',
            'airbags_seatbelts',
            'brakes_safety',
            'fuel_system',
            'steering_suspension',
        }
        caution_category_ids = {
            'electrical_system',
            'engine',
            'power_train',
            'visibility_lighting',
            'wheels_tires',
            'structure_body',
        }

        if complaint.crash or complaint.fire:
            return "unsafe", "Crash/fire was flagged, so the vehicle should not be driven until inspected."
        if complaint.predicted_category in critical_category_ids:
            return "caution", "This category can become safety-critical quickly, so inspect it before normal driving."
        if complaint.predicted_category in caution_category_ids:
            return "caution", "Short trips may be possible, but only after checking for warning lights, leaks, smoke, or abnormal noises."
        return "safe", "No critical flag is present, but the issue still needs diagnosis before it worsens."

    def _build_local_fallback_response(
        self,
        chat_session,
        user_message: str,
        rag_context: str = "",
    ) -> str:
        complaint = chat_session.complaint
        full_context = chat_session.build_full_context_for_llm(reference_query=user_message)
        uploaded_documents = full_context.get('uploaded_documents', [])
        resolved_document = chat_session.resolve_uploaded_document_reference(reference_query=user_message)
        resolved_document_context = None
        if resolved_document:
            resolved_document_context = next(
                (document for document in uploaded_documents if document['id'] == resolved_document['id']),
                None,
            )
        vehicle_name = chat_session.car.display_name
        category = complaint.get_predicted_category_display() if complaint.predicted_category else "Unclassified issue"
        safety_level, safety_note = self._assess_safety(chat_session)
        manual_hint = self._clean_provider_text(rag_context, max_len=420)
        language = self._detect_response_language(
            chat_session=chat_session,
            user_message=user_message,
            fallback_text=complaint.complaint_text,
        )
        is_arabic = language == "arabic"

        if is_arabic:
            analysis_lines = [
                f"- الشكوى الحالية أقرب إلى فئة `{category}` في السيارة {vehicle_name}.",
                f"- آخر رسالة منك تضيف هذه المعلومة: {self._clean_provider_text(user_message, max_len=220)}",
            ]
        else:
            analysis_lines = [
                f"- The current complaint is closest to the `{category}` area for {vehicle_name}.",
                f"- Your latest message adds this detail: {self._clean_provider_text(user_message, max_len=220)}",
            ]

        if manual_hint:
            analysis_lines.append(
                f"- {'سياق الدليل أو المرجع المرتبط' if is_arabic else 'Related manual context'}: {manual_hint}"
            )
        else:
            analysis_lines.append(
                "- لم يكن استرجاع الدليل الفني متاحًا في مسار الطوارئ، لذلك هذا الرد مبني على وصف الشكوى وسياق السيارة."
                if is_arabic else
                "- Manual retrieval was not available in the fallback path, so this answer is based on complaint history and vehicle context."
            )
        if resolved_document:
            if is_arabic:
                analysis_lines.append(
                    f"- غالبًا هذه الرسالة تشير إلى الملف المرفوع `{resolved_document['file_name']}` "
                    f"وحالته الآن `{self._document_status_label(resolved_document)}`."
                )
            else:
                analysis_lines.append(
                    f"- This turn most likely refers to the uploaded document `{resolved_document['file_name']}` "
                    f"with status `{self._document_status_label(resolved_document)}`."
                )
            if resolved_document_context and resolved_document_context.get('excerpts'):
                analysis_lines.append(
                    f"- {'أول مقتطف مفهرس من هذا الملف' if is_arabic else 'First indexed excerpt from that document'}: "
                    f"{resolved_document_context['excerpts'][0]['text']}"
                )
            elif not resolved_document.get('is_analyzed'):
                analysis_lines.append(
                    "- الملف مرفوع، لكن الفهرسة الخلفية ما زالت تعمل، لذلك المتاح حاليًا هو البيانات الأساسية فقط."
                    if is_arabic else
                    "- The file is uploaded, but background indexing is still running, so only metadata is available right now."
                )
        if uploaded_documents:
            uploaded_file_names = ", ".join(document['file_name'] for document in uploaded_documents)
            analysis_lines.append(
                f"- {'الملفات المرفوعة المرتبطة بهذه الشكوى حاليًا' if is_arabic else 'Uploaded complaint documents currently linked to this complaint'}: {uploaded_file_names}"
            )
        else:
            analysis_lines.append(
                "- لا توجد حاليًا ملفات مرفوعة خاصة بهذه الشكوى."
                if is_arabic else
                "- No complaint-specific uploaded documents are currently attached to this complaint."
            )

        if is_arabic:
            return "\n".join([
                "مزود الذكاء الاصطناعي المباشر غير متاح مؤقتًا، لذلك هذا رد احتياطي مبني على السياق المتاح.",
                "",
                "1) فهم المشكلة الحالية",
                f"- السيارة: {vehicle_name}",
                f"- فئة الشكوى المتوقعة: {category}",
                f"- نص الشكوى الأصلي: {self._clean_provider_text(complaint.complaint_text, max_len=260)}",
                "",
                "2) التحليل الفني المرتبط بهذه السيارة",
                *analysis_lines,
                "",
                "3) تقييم السلامة",
                f"- {safety_level.upper()}: {safety_note}",
                "",
                "4) خطة العمل والخطوات التالية",
                "1. اقرأ أكواد الأعطال المخزنة والمعلقة من كل الوحدات ذات الصلة.",
                "2. حدّد متى تظهر الأعراض: مع التشغيل البارد أو بعد السخونة أو أثناء التسارع أو الفرملة أو المطبات.",
                "3. افحص أي تسريب ظاهر أو فيش مرتخية أو فيوزات تالفة أو آثار حرارة أو روائح غير طبيعية أو دخان.",
                "4. قارن العرض الحالي بتاريخ الشكاوى السابقة لنفس السيارة قبل تغيير أي قطعة.",
                "5. إذا ظهرت لمبات تحذير أو تقطيع شديد أو رائحة وقود أو ضعف فرامل أو سخونة زائدة، أوقف القيادة وافحص السيارة فورًا.",
            ])

        return "\n".join([
            "The live AI provider is temporarily unavailable, so this is a fallback diagnostic response.",
            "",
            "1) Understanding the current issue",
            f"- Vehicle: {vehicle_name}",
            f"- Predicted complaint category: {category}",
            f"- Original complaint: {self._clean_provider_text(complaint.complaint_text, max_len=260)}",
            "",
            "2) Technical analysis linked to this exact vehicle",
            *analysis_lines,
            "",
            "3) Safety assessment (safe/caution/unsafe)",
            f"- {safety_level.upper()}: {safety_note}",
            "",
            "4) Action plan with numbered diagnostic and repair steps",
            "1. Read stored and pending diagnostic trouble codes from all relevant modules.",
            "2. Confirm when the symptom happens: cold start, hot engine, acceleration, braking, steering load, or rough road.",
            "3. Check for visible leaks, loose connectors, blown fuses, heat damage, and abnormal smells or smoke.",
            "4. Compare the symptom with previous complaints for this vehicle before replacing parts.",
            "5. If warning lights, misfire, fuel smell, brake weakness, steering instability, or overheating are present, stop driving and inspect immediately.",
        ])

    def _generate_with_fallback_provider(
        self,
        chat_session,
        user_message: str,
        use_conversation_memory: bool = True,
        extra_context: Optional[str] = None,
    ) -> Optional[str]:
        if self.provider != "cohere" and self.llm is not None:
            provider_name = self.provider
            llm = self.llm
        else:
            provider_name, llm = self._ensure_fallback_provider()

        if llm is None:
            return None

        try:
            messages = self._build_langchain_messages(
                chat_session=chat_session,
                user_message=user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=extra_context,
            )
            response = llm.invoke(messages)
            content = getattr(response, 'content', response)
            if not content:
                return None
            return self._ensure_response_language(
                chat_session=chat_session,
                user_message=user_message,
                response_text=str(content).strip(),
            )
        except Exception as exc:
            self._log_provider_failure(
                provider=provider_name,
                operation="fallback-chat",
                exc=exc,
                fallback_target="deterministic-response",
            )
            return None

    def _prepare_user_message(self, user_message: str, image_paths: Optional[Iterable[str]]) -> str:
        if image_paths and self.cohere_image_chat_enabled:
            return user_message
        image_summary = self._analyze_images(image_paths, user_message)
        if not image_summary:
            return user_message
        return (
            f"{user_message}\n\n"
            "IMAGE ANALYSIS CONTEXT\n"
            f"{image_summary}"
        )

    def generate_chat_response(
        self,
        session_id: int,
        user_message: str,
        image_paths: Optional[Iterable[str]] = None
    ):
        """Entry point used by some callers."""
        from apps.chat.models import ChatSession

        session = ChatSession.objects.select_related('complaint__car__customer').get(id=session_id)
        return self.generate_response(
            user_message=user_message,
            chat_session=session,
            use_conversation_memory=True,
            image_paths=image_paths,
        )

    def generate_response(
        self,
        user_message: str,
        chat_session,
        use_conversation_memory: bool = True,
        image_paths: Optional[Iterable[str]] = None
    ) -> str:
        """Return non-streamed assistant response."""
        normalized_image_paths = self._normalize_image_paths(image_paths)
        final_user_message = self._prepare_user_message(user_message, normalized_image_paths)
        direct_document_response = self._build_uploaded_document_summary_response(
            chat_session=chat_session,
            user_message=final_user_message,
        )
        if direct_document_response:
            return direct_document_response

        if self._should_use_cohere_vision(normalized_image_paths):
            try:
                messages = self._build_multimodal_cohere_messages(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    use_conversation_memory=use_conversation_memory,
                )
                return self._ensure_response_language(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    response_text=cohere_service.chat_multimodal(
                        messages=messages,
                        model=self.cohere_vision_model,
                        temperature=0.2,
                        max_tokens=900,
                    ),
                )
            except Exception as exc:
                self._log_provider_failure(
                    provider="cohere",
                    operation="vision-chat",
                    exc=exc,
                    fallback_target="ollama-vision",
                )
                ollama_vision_response = self._generate_with_local_vision_provider(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    use_conversation_memory=use_conversation_memory,
                )
                if ollama_vision_response:
                    return self._ensure_response_language(
                        chat_session=chat_session,
                        user_message=final_user_message,
                        response_text=ollama_vision_response,
                    )
                fallback_user_message = self._build_image_fallback_user_message(final_user_message)
                if fallback_user_message:
                    rag_context = self._collect_rag_context(chat_session, fallback_user_message, top_k=3)
                    fallback_response = self._generate_with_fallback_provider(
                        chat_session=chat_session,
                        user_message=fallback_user_message,
                        use_conversation_memory=use_conversation_memory,
                        extra_context=rag_context if rag_context else None,
                    )
                    if fallback_response:
                        return (
                            f"{self._build_image_fallback_notice(final_user_message, str(exc))}\n\n"
                            f"{fallback_response}"
                        )
                return self._build_image_fallback_response(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    reason=str(exc),
                )
        elif normalized_image_paths:
            ollama_vision_response = self._generate_with_local_vision_provider(
                chat_session=chat_session,
                user_message=final_user_message,
                image_paths=normalized_image_paths,
                use_conversation_memory=use_conversation_memory,
            )
            if ollama_vision_response:
                return self._ensure_response_language(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    response_text=ollama_vision_response,
                )

        # Cohere path
        if self.provider == "cohere":
            try:
                messages = self._build_cohere_messages(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    use_conversation_memory=use_conversation_memory,
                )
                return self._ensure_response_language(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    response_text=cohere_service.chat(messages=messages, model=self.command_model),
                )
            except Exception as exc:
                self._log_provider_failure(
                    provider="cohere",
                    operation="chat",
                    exc=exc,
                    fallback_target="local-text",
                )
                rag_context = self._collect_rag_context(chat_session, final_user_message, top_k=3)
                fallback_response = self._generate_with_fallback_provider(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    use_conversation_memory=use_conversation_memory,
                    extra_context=rag_context if rag_context else None,
                )
                if fallback_response:
                    return fallback_response
                return self._build_local_fallback_response(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    rag_context=rag_context,
                )

        # Fallback path
        if not self.llm:
            rag_context = self._collect_rag_context(chat_session, final_user_message, top_k=3)
            fallback_response = self._generate_with_fallback_provider(
                chat_session=chat_session,
                user_message=final_user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=rag_context if rag_context else None,
            )
            if fallback_response:
                return fallback_response
            return self._build_local_fallback_response(
                chat_session=chat_session,
                user_message=final_user_message,
                rag_context=rag_context,
            )

        try:
            messages = self._build_langchain_messages(
                chat_session=chat_session,
                user_message=final_user_message,
                use_conversation_memory=use_conversation_memory,
            )
            response = self.llm.invoke(messages)
            return self._ensure_response_language(
                chat_session=chat_session,
                user_message=final_user_message,
                response_text=response.content,
            )
        except Exception as exc:
            self._log_provider_failure(
                provider=self.provider,
                operation="chat",
                exc=exc,
                fallback_target="deterministic-response",
            )
            return self._build_local_fallback_response(
                chat_session=chat_session,
                user_message=final_user_message,
                rag_context="",
            )

    def stream_response(
        self,
        user_message: str,
        chat_session,
        use_conversation_memory: bool = True,
        image_paths: Optional[Iterable[str]] = None
    ):
        """Stream response chunks."""
        normalized_image_paths = self._normalize_image_paths(image_paths)
        final_user_message = self._prepare_user_message(user_message, normalized_image_paths)
        direct_document_response = self._build_uploaded_document_summary_response(
            chat_session=chat_session,
            user_message=final_user_message,
        )
        if direct_document_response:
            for chunk in self._stream_text_chunks(direct_document_response):
                yield chunk
            return

        if self._should_use_cohere_vision(normalized_image_paths):
            try:
                messages = self._build_multimodal_cohere_messages(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    use_conversation_memory=use_conversation_memory,
                )
                for chunk in cohere_service.chat_stream_multimodal(
                    messages=messages,
                    model=self.cohere_vision_model,
                    temperature=0.2,
                    max_tokens=900,
                ):
                    if chunk:
                        yield chunk
                return
            except Exception as exc:
                self._log_provider_failure(
                    provider="cohere",
                    operation="vision-stream",
                    exc=exc,
                    fallback_target="ollama-vision",
                )
                ollama_vision_stream = self._stream_with_local_vision_provider(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    use_conversation_memory=use_conversation_memory,
                )
                if ollama_vision_stream is not None:
                    buffered_response = "".join(chunk for chunk in ollama_vision_stream if chunk)
                    finalized_response = self._ensure_response_language(
                        chat_session=chat_session,
                        user_message=final_user_message,
                        response_text=buffered_response,
                    )
                    for chunk in self._stream_text_chunks(finalized_response or buffered_response):
                        yield chunk
                    return
                fallback_user_message = self._build_image_fallback_user_message(final_user_message)
                if fallback_user_message:
                    rag_context = self._collect_rag_context(chat_session, fallback_user_message, top_k=3)
                    fallback_response = self._generate_with_fallback_provider(
                        chat_session=chat_session,
                        user_message=fallback_user_message,
                        use_conversation_memory=use_conversation_memory,
                        extra_context=rag_context if rag_context else None,
                    )
                    if fallback_response:
                        fallback_text = (
                            f"{self._build_image_fallback_notice(final_user_message, str(exc))}\n\n"
                            f"{fallback_response}"
                        )
                        for chunk in self._stream_text_chunks(fallback_text):
                            yield chunk
                        return
                fallback_text = self._build_image_fallback_response(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    image_paths=normalized_image_paths,
                    reason=str(exc),
                )
                for chunk in self._stream_text_chunks(fallback_text):
                    yield chunk
                return
        elif normalized_image_paths:
            ollama_vision_stream = self._stream_with_local_vision_provider(
                chat_session=chat_session,
                user_message=final_user_message,
                image_paths=normalized_image_paths,
                use_conversation_memory=use_conversation_memory,
            )
            if ollama_vision_stream is not None:
                buffered_response = "".join(chunk for chunk in ollama_vision_stream if chunk)
                finalized_response = self._ensure_response_language(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    response_text=buffered_response,
                )
                for chunk in self._stream_text_chunks(finalized_response or buffered_response):
                    yield chunk
                return

        rag_context = self._collect_rag_context(chat_session, final_user_message, top_k=3)

        # Cohere path
        if self.provider == "cohere":
            try:
                messages = self._build_cohere_messages(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    use_conversation_memory=use_conversation_memory,
                    extra_context=rag_context if rag_context else None,
                )
                for chunk in cohere_service.chat_stream(messages=messages, model=self.command_model):
                    if chunk:
                        yield chunk
                return
            except Exception as exc:
                self._log_provider_failure(
                    provider="cohere",
                    operation="stream",
                    exc=exc,
                    fallback_target="local-text",
                )
                fallback_response = self._generate_with_fallback_provider(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    use_conversation_memory=use_conversation_memory,
                    extra_context=rag_context if rag_context else None,
                )
                if fallback_response:
                    for chunk in self._stream_text_chunks(fallback_response):
                        yield chunk
                    return
                for chunk in self._stream_text_chunks(self._build_local_fallback_response(
                    chat_session=chat_session,
                    user_message=final_user_message,
                    rag_context=rag_context,
                )):
                    yield chunk
                return

        # Fallback path
        if not self.llm:
            fallback_response = self._generate_with_fallback_provider(
                chat_session=chat_session,
                user_message=final_user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=rag_context if rag_context else None,
            )
            if fallback_response:
                for chunk in self._stream_text_chunks(fallback_response):
                    yield chunk
                return
            for chunk in self._stream_text_chunks(self._build_local_fallback_response(
                chat_session=chat_session,
                user_message=final_user_message,
                rag_context=rag_context,
            )):
                yield chunk
            return

        try:
            messages = self._build_langchain_messages(
                chat_session=chat_session,
                user_message=final_user_message,
                use_conversation_memory=use_conversation_memory,
                extra_context=rag_context if rag_context else None,
            )
            for chunk in self.llm.stream(messages):
                if getattr(chunk, 'content', ''):
                    yield chunk.content
        except Exception as exc:
            self._log_provider_failure(
                provider=self.provider,
                operation="stream",
                exc=exc,
                fallback_target="deterministic-response",
            )
            for chunk in self._stream_text_chunks(self._build_local_fallback_response(
                chat_session=chat_session,
                user_message=final_user_message,
                rag_context=rag_context,
            )):
                yield chunk

    def generate_initial_greeting(self, chat_session) -> str:
        """Create first assistant message for a new session."""
        prompt = (
            "A customer has just created a complaint. "
            "Provide a concise first diagnostic overview and ask 2 focused follow-up questions."
        )

        if self.provider == "cohere":
            try:
                messages = self._build_cohere_messages(
                    chat_session=chat_session,
                    user_message=prompt,
                    use_conversation_memory=False,
                )
                return cohere_service.chat(messages=messages, model=self.command_model)
            except Exception as exc:
                self._log_provider_failure(
                    provider="cohere",
                    operation="greeting",
                    exc=exc,
                    fallback_target="local-text",
                )
                fallback_response = self._generate_with_fallback_provider(
                    chat_session=chat_session,
                    user_message=prompt,
                    use_conversation_memory=False,
                )
                if fallback_response:
                    return fallback_response

        if self.llm:
            try:
                messages = self._build_langchain_messages(
                    chat_session=chat_session,
                    user_message=prompt,
                    use_conversation_memory=False,
                )
                response = self.llm.invoke(messages)
                return response.content
            except Exception as exc:
                self._log_provider_failure(
                    provider=self.provider,
                    operation="greeting",
                    exc=exc,
                    fallback_target="deterministic-response",
                )

        complaint = chat_session.complaint
        return (
            f"Hello. I reviewed your complaint for {complaint.car.display_name}. "
            f"Current predicted category is {complaint.get_predicted_category_display()}. "
            "Please share when the issue appears and any warning lights you see."
        )


_mechanic_service = None


def get_mechanic_service() -> MechanicChatService:
    """Singleton accessor."""
    global _mechanic_service
    if _mechanic_service is None:
        _mechanic_service = MechanicChatService()
    return _mechanic_service


def chat_with_mechanic(user_message: str, chat_session, use_memory: bool = True) -> str:
    """Convenience chat helper."""
    service = get_mechanic_service()
    return service.generate_response(
        user_message=user_message,
        chat_session=chat_session,
        use_conversation_memory=use_memory,
    )
