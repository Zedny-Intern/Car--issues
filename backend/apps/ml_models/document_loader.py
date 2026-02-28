"""
Document loader for multimodal RAG.

Capabilities:
- PDF and text document chunking
- PDF image extraction
- Caption/nearby text linking for extracted images
- Optional Cohere vision summaries for images
- Standalone image indexing
"""
import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings

from .cohere_service import cohere_service

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF is not available for PDF image extraction")

try:
    from langchain_community.document_loaders import PyMuPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    PyMuPDFLoader = None
    RecursiveCharacterTextSplitter = None
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain loaders are not available")


class DocumentLoader:
    """
    Multimodal document loader for text + image aware RAG indexing.
    """

    SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
    SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.md'}
    SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
    SUPPORTED_DOCUMENT_EXTENSIONS = (
        SUPPORTED_PDF_EXTENSIONS
        | SUPPORTED_TEXT_EXTENSIONS
        | SUPPORTED_IMAGE_EXTENSIONS
    )

    def __init__(self):
        self.static_dir = str(getattr(
            settings, 'RAG_DATA_STATIC_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'static'
        ))
        self.uploads_dir = str(getattr(
            settings, 'RAG_DATA_UPLOADS_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'uploads'
        ))
        self.complaint_docs_dir = str(getattr(
            settings, 'RAG_COMPLAINT_DOCS_DIR',
            Path(settings.MEDIA_ROOT) / 'complaint_docs'
        ))
        self.rag_data_dir = str(getattr(
            settings, 'RAG_DATA_DIR',
            Path(settings.BASE_DIR).parent / 'rag data'
        ))
        self.extracted_images_dir = str(getattr(
            settings, 'RAG_EXTRACTED_IMAGES_DIR',
            Path(settings.BASE_DIR).parent / 'data' / 'extracted_images'
        ))

        for directory in [self.static_dir, self.uploads_dir, self.complaint_docs_dir, self.extracted_images_dir]:
            os.makedirs(directory, exist_ok=True)

        self.max_images_per_document = int(getattr(settings, 'RAG_MAX_IMAGES_PER_DOCUMENT', 80))
        self.use_vision_on_index = bool(getattr(settings, 'RAG_USE_VISION_ON_INDEX', True))

        self.text_splitter = None
        if LANGCHAIN_AVAILABLE:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )

        self._vector_store = None
        self._sync_lock = threading.Lock()
        self._last_sync_completed_at = 0.0
        self._last_sync_result: Dict = {}

    @property
    def vector_store(self):
        if self._vector_store is None:
            from .multimodal_vector_store import multimodal_vector_store
            self._vector_store = multimodal_vector_store
        return self._vector_store

    @staticmethod
    def _clean_text(text: str, max_len: Optional[int] = None) -> str:
        normalized = " ".join((text or "").replace("\x00", " ").split())
        if max_len and len(normalized) > max_len:
            return normalized[:max_len]
        return normalized

    def compute_file_hash(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as file_handle:
                for byte_block in iter(lambda: file_handle.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError:
            return ""

    def get_file_type(self, file_path: str) -> Optional[str]:
        ext = Path(file_path).suffix.lower()
        if ext in self.SUPPORTED_PDF_EXTENSIONS:
            return 'pdf'
        if ext in self.SUPPORTED_TEXT_EXTENSIONS:
            return 'text'
        if ext in self.SUPPORTED_IMAGE_EXTENSIONS:
            return 'image'
        return None

    def scan_all_directories(self) -> Dict[str, List[str]]:
        result = {'static': [], 'uploads': [], 'complaint_docs': [], 'rag_data': []}
        for key, directory in [
            ('static', self.static_dir),
            ('uploads', self.uploads_dir),
            ('complaint_docs', self.complaint_docs_dir),
            ('rag_data', self.rag_data_dir),
        ]:
            if not os.path.exists(directory):
                continue
            for root, _, files in os.walk(directory):
                for file_name in files:
                    path = os.path.join(root, file_name)
                    if self.get_file_type(path):
                        result[key].append(path)
        return result

    def is_already_indexed(self, file_path: str) -> bool:
        try:
            from .models import DocumentMetadata

            document = DocumentMetadata.objects.only('file_hash', 'indexed').filter(file_path=file_path).first()
            if not document or not document.indexed:
                return False

            current_hash = self.compute_file_hash(file_path)
            return bool(current_hash and current_hash == document.file_hash)
        except Exception:
            return False

    def needs_indexing(self, file_path: str) -> bool:
        try:
            from .models import DocumentMetadata

            document = DocumentMetadata.objects.only('file_hash', 'file_type', 'indexed').filter(
                file_path=file_path
            ).first()
            if document is None or not document.indexed:
                return True

            current_hash = self.compute_file_hash(file_path)
            current_type = self.get_file_type(file_path)
            return not current_hash or document.file_hash != current_hash or document.file_type != current_type
        except Exception:
            return True

    def _invalidate_runtime_caches(self):
        try:
            from .rag_agent import multimodal_rag_agent

            multimodal_rag_agent.invalidate_cache()
        except Exception as exc:
            logger.warning("Failed to invalidate RAG cache: %s", exc)

    def _cleanup_extracted_assets_for_hash(self, file_hash: str):
        if not file_hash:
            return

        prefix = f"{file_hash[:12]}_"
        try:
            for entry in os.listdir(self.extracted_images_dir):
                if entry.startswith(prefix):
                    try:
                        os.remove(os.path.join(self.extracted_images_dir, entry))
                    except OSError:
                        logger.warning("Failed to delete extracted image asset %s", entry)
        except FileNotFoundError:
            return

    def _remove_missing_documents(self, available_paths: set[str]) -> int:
        from .models import DocumentMetadata

        removed = 0
        for document in DocumentMetadata.objects.all().only('id', 'file_path', 'file_hash', 'file_type'):
            if document.file_path in available_paths:
                continue

            self.vector_store.delete_by_file_hash(document.file_hash)
            if document.file_type == 'pdf':
                self._cleanup_extracted_assets_for_hash(document.file_hash)
            document.delete()
            removed += 1

        if removed:
            self._invalidate_runtime_caches()
        return removed

    @staticmethod
    def _extract_blocks(page) -> List[Dict]:
        """Extract text blocks with geometry from a PDF page."""
        blocks_data = []
        for block in page.get_text("blocks") or []:
            if len(block) < 5:
                continue
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            cleaned = " ".join((text or "").split())
            if cleaned:
                blocks_data.append({
                    "x0": float(x0),
                    "y0": float(y0),
                    "x1": float(x1),
                    "y1": float(y1),
                    "text": cleaned,
                })
        return blocks_data

    @staticmethod
    def _x_overlap_ratio(rect, block: Dict) -> float:
        if rect is None:
            return 0.0
        overlap = max(0.0, min(rect.x1, block["x1"]) - max(rect.x0, block["x0"]))
        image_width = max(1.0, rect.x1 - rect.x0)
        return overlap / image_width

    def _link_image_with_text(
        self,
        rect,
        blocks: List[Dict],
        page_text: str
    ) -> Tuple[str, str]:
        """
        Link extracted image with likely caption and nearby explanatory text.
        """
        if not blocks:
            fallback = self._clean_text(page_text, max_len=500)
            return "", fallback

        if rect is None:
            nearby = " ".join(b["text"] for b in blocks[:3])
            return "", self._clean_text(nearby, max_len=700)

        caption_candidates = []
        above_candidates = []
        below_candidates = []

        for block in blocks:
            overlap = self._x_overlap_ratio(rect, block)
            center_distance = abs(((block["y0"] + block["y1"]) / 2.0) - ((rect.y0 + rect.y1) / 2.0))
            if block["y0"] >= rect.y1 and (block["y0"] - rect.y1) <= 140:
                caption_candidates.append((block, overlap, block["y0"] - rect.y1))
            if block["y1"] <= rect.y0:
                above_candidates.append((block, center_distance))
            if block["y0"] >= rect.y1:
                below_candidates.append((block, center_distance))

        caption_text = ""
        if caption_candidates:
            # Prefer horizontal overlap and short vertical distance.
            caption_candidates.sort(key=lambda item: (-item[1], item[2]))
            best_caption = caption_candidates[0][0]["text"]
            caption_text = self._clean_text(best_caption, max_len=260)

        if not caption_text:
            # Fallback: pick text mentioning figure/image near the image area.
            figure_keywords = ("figure", "fig.", "fig ", "image", "photo", "diagram")
            nearby_blocks = [
                b for b in blocks
                if abs(((b["y0"] + b["y1"]) / 2.0) - ((rect.y0 + rect.y1) / 2.0)) <= 180
            ]
            for block in nearby_blocks:
                lowered = block["text"].lower()
                if any(keyword in lowered for keyword in figure_keywords):
                    caption_text = self._clean_text(block["text"], max_len=260)
                    break

        above_text = ""
        below_text = ""
        if above_candidates:
            above_candidates.sort(key=lambda item: item[1])
            above_text = above_candidates[0][0]["text"]
        if below_candidates:
            below_candidates.sort(key=lambda item: item[1])
            below_text = below_candidates[0][0]["text"]

        nearby_parts = []
        if above_text:
            nearby_parts.append(f"Text above image: {self._clean_text(above_text, 320)}")
        if below_text and self._clean_text(below_text, 320) != self._clean_text(caption_text, 320):
            nearby_parts.append(f"Text below image: {self._clean_text(below_text, 320)}")
        if not nearby_parts:
            nearby_parts.append(self._clean_text(page_text, max_len=500))

        return caption_text, " | ".join(nearby_parts)

    def _vision_summary(self, image_path: str, hint_text: str) -> str:
        if not (self.use_vision_on_index and cohere_service.is_available):
            return ""
        try:
            prompt = (
                "Analyze this technical automotive image and summarize what is visible. "
                "Focus on parts, faults, and actionable diagnostics. "
                f"Related text: {hint_text}"
            )
            summary = cohere_service.describe_image(image_path, question=prompt)
            if summary.lower().startswith("image analysis failed"):
                return ""
            return self._clean_text(summary, max_len=1200)
        except Exception as exc:
            logger.warning("Vision summary failed for %s: %s", image_path, exc)
            return ""

    def _extract_pdf_image_docs(
        self,
        file_path: str,
        file_hash: str,
        file_name: str
    ) -> List[Dict]:
        if not PYMUPDF_AVAILABLE:
            return []

        image_docs: List[Dict] = []
        extracted_count = 0

        pdf_document = fitz.open(file_path)
        try:
            for page_idx in range(pdf_document.page_count):
                if extracted_count >= self.max_images_per_document:
                    break

                page = pdf_document.load_page(page_idx)
                page_number = page_idx + 1
                page_text = self._clean_text(page.get_text("text"), max_len=1800)
                blocks = self._extract_blocks(page)
                page_images = page.get_images(full=True) or []

                for image_idx, image_data in enumerate(page_images, start=1):
                    if extracted_count >= self.max_images_per_document:
                        break

                    xref = image_data[0]
                    base_image = pdf_document.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image.get("image")
                    image_ext = base_image.get("ext", "png")
                    if not image_bytes:
                        continue

                    image_filename = f"{file_hash[:12]}_p{page_number}_x{xref}_{image_idx}.{image_ext}"
                    extracted_image_path = os.path.join(self.extracted_images_dir, image_filename)
                    if not os.path.exists(extracted_image_path):
                        with open(extracted_image_path, "wb") as image_file:
                            image_file.write(image_bytes)

                    rect = None
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            rect = rects[0]
                    except Exception:
                        rect = None

                    caption, nearby_text = self._link_image_with_text(rect, blocks, page_text)
                    vision_summary = self._vision_summary(
                        extracted_image_path,
                        f"Caption: {caption}. Nearby: {nearby_text}"
                    )

                    chunk_id = f"img_{file_hash[:8]}_{page_number}_{image_idx}"
                    content_parts = [
                        f"Image from {file_name}, page {page_number}.",
                        f"Caption: {caption}" if caption else "",
                        f"Nearby text: {nearby_text}" if nearby_text else "",
                        f"Vision summary: {vision_summary}" if vision_summary else "",
                    ]
                    chunk_content = "\n".join(part for part in content_parts if part).strip()
                    if not chunk_content:
                        chunk_content = f"Image extracted from {file_name}, page {page_number}."

                    image_docs.append({
                        'id': chunk_id,
                        'content': chunk_content,
                        'metadata': {
                            'file_hash': file_hash,
                            'file_name': file_name,
                            'page': page_number,
                            'chunk_id': chunk_id,
                            'source': file_path,
                            'chunk_type': 'image',
                            'image_path': extracted_image_path,
                            'caption': caption or "",
                        }
                    })
                    extracted_count += 1
        finally:
            pdf_document.close()

        return image_docs

    def _save_text_chunks(
        self,
        file_path: str,
        file_hash: str,
        file_name: str,
        documents
    ) -> List[Dict]:
        chunks = self.text_splitter.split_documents(documents)
        text_docs = []

        for index, chunk in enumerate(chunks):
            content = self._clean_text(chunk.page_content)
            if not (content and content.strip()):
                continue

            chunk_id = f"txt_{file_hash[:8]}_{index}"
            page_num = chunk.metadata.get('page', 0) + 1
            text_docs.append({
                'id': chunk_id,
                'content': content,
                'metadata': {
                    'file_hash': file_hash,
                    'file_name': file_name,
                    'page': page_num,
                    'chunk_id': chunk_id,
                    'source': file_path,
                    'chunk_type': 'text',
                }
            })

        return text_docs

    def _persist_chunks(self, doc_metadata, text_docs: List[Dict], image_docs: List[Dict]):
        from .models import DocumentChunk

        # Reset chunks for this document on re-index.
        DocumentChunk.objects.filter(document=doc_metadata).delete()

        for doc in text_docs:
            metadata = doc['metadata']
            DocumentChunk.objects.update_or_create(
                chunk_id=doc['id'],
                defaults={
                    'document': doc_metadata,
                    'chunk_type': 'text',
                    'page_number': metadata.get('page', 1),
                    'content': doc['content'][:5000],
                    'text_vector_id': doc['id'],
                }
            )

        for doc in image_docs:
            metadata = doc['metadata']
            DocumentChunk.objects.update_or_create(
                chunk_id=doc['id'],
                defaults={
                    'document': doc_metadata,
                    'chunk_type': 'image',
                    'page_number': metadata.get('page', 1),
                    'content': doc['content'][:5000],
                    'image_path': metadata.get('image_path'),
                    'caption': metadata.get('caption') or None,
                    'text_vector_id': doc['id'],
                }
            )

    def process_document(self, file_path: str) -> Dict:
        from .models import DocumentMetadata

        logger.info("Processing file for multimodal RAG: %s", file_path)

        if not LANGCHAIN_AVAILABLE:
            return {'success': False, 'error': 'LangChain not available'}

        file_hash = self.compute_file_hash(file_path)
        file_name = os.path.basename(file_path)
        file_type = self.get_file_type(file_path)
        if file_type not in {'pdf', 'text'}:
            return {'success': False, 'error': 'Unsupported document type'}

        try:
            existing_metadata = DocumentMetadata.objects.filter(file_path=file_path).first()
            previous_hash = existing_metadata.file_hash if existing_metadata else ""
            if previous_hash and previous_hash != file_hash:
                self.vector_store.delete_by_file_hash(previous_hash)
                self._cleanup_extracted_assets_for_hash(previous_hash)

            if file_type == 'text':
                from langchain_community.document_loaders import TextLoader
                loader = TextLoader(file_path, encoding='utf-8')
            else:
                loader = PyMuPDFLoader(file_path)

            documents = loader.load()

            doc_metadata, _ = DocumentMetadata.objects.update_or_create(
                file_path=file_path,
                defaults={
                    'file_name': file_name,
                    'file_hash': file_hash,
                    'file_type': file_type,
                    'file_size': os.path.getsize(file_path),
                    'page_count': len(documents),
                    'indexed': False,
                }
            )

            text_docs = self._save_text_chunks(
                file_path=file_path,
                file_hash=file_hash,
                file_name=file_name,
                documents=documents,
            )
            image_docs = []
            if file_type == 'pdf':
                image_docs = self._extract_pdf_image_docs(
                    file_path=file_path,
                    file_hash=file_hash,
                    file_name=file_name,
                )

            self.vector_store.delete_by_file_hash(file_hash)
            all_docs = text_docs + image_docs
            if all_docs:
                self.vector_store.add_text_documents(all_docs)

            self._persist_chunks(doc_metadata, text_docs, image_docs)
            doc_metadata.mark_indexed()
            self._invalidate_runtime_caches()

            return {
                'success': True,
                'file_path': file_path,
                'text_chunks': len(text_docs),
                'image_chunks': len(image_docs),
                'pages': len(documents),
                'loader': 'Multimodal Loader',
            }
        except Exception as exc:
            logger.error("Error processing document %s: %s", file_path, exc)
            try:
                doc = DocumentMetadata.objects.get(file_path=file_path)
                doc.mark_error(str(exc))
            except Exception:
                pass
            return {'success': False, 'error': str(exc)}

    def process_image(self, file_path: str) -> Dict:
        from .models import DocumentMetadata, DocumentChunk

        logger.info("Processing standalone image for RAG: %s", file_path)
        file_hash = self.compute_file_hash(file_path)
        file_name = os.path.basename(file_path)

        try:
            existing_metadata = DocumentMetadata.objects.filter(file_path=file_path).first()
            previous_hash = existing_metadata.file_hash if existing_metadata else ""
            if previous_hash and previous_hash != file_hash:
                self.vector_store.delete_by_file_hash(previous_hash)

            doc_metadata, _ = DocumentMetadata.objects.update_or_create(
                file_path=file_path,
                defaults={
                    'file_name': file_name,
                    'file_hash': file_hash,
                    'file_type': 'image',
                    'file_size': os.path.getsize(file_path),
                    'page_count': 1,
                    'indexed': False,
                }
            )

            caption_guess = self._clean_text(Path(file_name).stem.replace('_', ' '), max_len=180)
            vision_summary = self._vision_summary(file_path, f"File name hint: {caption_guess}")

            chunk_id = f"img_{file_hash[:8]}_1_1"
            content_parts = [
                f"Standalone uploaded image: {file_name}.",
                f"Caption hint: {caption_guess}" if caption_guess else "",
                f"Vision summary: {vision_summary}" if vision_summary else "",
            ]
            chunk_content = "\n".join(part for part in content_parts if part).strip()
            if not chunk_content:
                chunk_content = f"Standalone uploaded image: {file_name}."

            image_doc = {
                'id': chunk_id,
                'content': chunk_content,
                'metadata': {
                    'file_hash': file_hash,
                    'file_name': file_name,
                    'page': 1,
                    'chunk_id': chunk_id,
                    'source': file_path,
                    'chunk_type': 'image',
                    'image_path': file_path,
                    'caption': caption_guess,
                }
            }

            self.vector_store.delete_by_file_hash(file_hash)
            self.vector_store.add_text_documents([image_doc])

            DocumentChunk.objects.filter(document=doc_metadata).delete()
            DocumentChunk.objects.update_or_create(
                chunk_id=chunk_id,
                defaults={
                    'document': doc_metadata,
                    'chunk_type': 'image',
                    'page_number': 1,
                    'content': chunk_content[:5000],
                    'image_path': file_path,
                    'caption': caption_guess or None,
                    'text_vector_id': chunk_id,
                }
            )

            doc_metadata.mark_indexed()
            self._invalidate_runtime_caches()
            return {
                'success': True,
                'file_path': file_path,
                'text_chunks': 0,
                'image_chunks': 1,
                'pages': 1,
                'loader': 'Multimodal Loader',
            }
        except Exception as exc:
            logger.error("Error processing standalone image %s: %s", file_path, exc)
            try:
                doc = DocumentMetadata.objects.get(file_path=file_path)
                doc.mark_error(str(exc))
            except Exception:
                pass
            return {'success': False, 'error': str(exc)}

    def process_file(self, file_path: str, force: bool = False) -> Dict:
        if not force and self.is_already_indexed(file_path):
            return {'success': True, 'skipped': True}

        file_type = self.get_file_type(file_path)
        if file_type in {'pdf', 'text'}:
            return self.process_document(file_path)
        if file_type == 'image':
            return self.process_image(file_path)
        return {'success': False, 'error': 'Unsupported file type'}

    def sync_all_documents(self, force: bool = False, cleanup_missing: bool = True) -> Dict:
        all_files = self.scan_all_directories()
        available_paths = {
            path
            for files in all_files.values()
            for path in files
        }
        results = {
            'total': 0,
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'removed': 0,
            'loader': 'Multimodal Loader' if LANGCHAIN_AVAILABLE else 'N/A',
        }

        if cleanup_missing:
            try:
                results['removed'] = self._remove_missing_documents(available_paths)
            except Exception as exc:
                logger.error("Failed to clean up deleted documents: %s", exc)

        for files in all_files.values():
            for path in files:
                results['total'] += 1
                try:
                    result = self.process_file(path, force=force)
                    if result.get('skipped'):
                        results['skipped'] += 1
                    elif result.get('success'):
                        results['processed'] += 1
                    else:
                        results['errors'] += 1
                except Exception as exc:
                    results['errors'] += 1
                    logger.error("Indexing error for %s: %s", path, exc)

        self._last_sync_completed_at = time.time()
        self._last_sync_result = dict(results)
        return results

    def index_all_documents(self, force: bool = False) -> Dict:
        return self.sync_all_documents(force=force, cleanup_missing=True)

    def maybe_sync_all_documents(
        self,
        force: bool = False,
        cleanup_missing: bool = True,
        min_interval_seconds: int = 30,
    ) -> Dict:
        now = time.time()
        if (
            not force
            and self._last_sync_completed_at
            and (now - self._last_sync_completed_at) < float(min_interval_seconds)
        ):
            return {
                'success': True,
                'skipped': True,
                'reason': 'recent_sync',
                'last_result': self._last_sync_result,
            }

        if not self._sync_lock.acquire(blocking=False):
            return {
                'success': True,
                'skipped': True,
                'reason': 'sync_in_progress',
                'last_result': self._last_sync_result,
            }

        try:
            result = self.sync_all_documents(force=force, cleanup_missing=cleanup_missing)
            result['success'] = True
            return result
        finally:
            self._sync_lock.release()

    def get_statistics(self) -> Dict:
        from .models import DocumentMetadata, DocumentChunk

        all_files = self.scan_all_directories()
        return {
            'directories': {
                'static': self.static_dir,
                'uploads': self.uploads_dir,
                'complaint_docs': self.complaint_docs_dir,
                'rag_data': self.rag_data_dir,
                'extracted_images': self.extracted_images_dir,
            },
            'files_on_disk': sum(len(files) for files in all_files.values()),
            'documents_in_db': DocumentMetadata.objects.count(),
            'indexed_documents': DocumentMetadata.objects.filter(indexed=True).count(),
            'total_chunks': DocumentChunk.objects.count(),
            'langchain_available': LANGCHAIN_AVAILABLE,
            'pymupdf_available': PYMUPDF_AVAILABLE,
            'vision_indexing_enabled': self.use_vision_on_index and cohere_service.is_available,
            'vector_store': self.vector_store.get_statistics(),
            'last_sync_completed_at': self._last_sync_completed_at,
            'last_sync_result': self._last_sync_result,
        }


document_loader = DocumentLoader()


def startup_index_documents():
    """Startup indexing helper."""
    logger.info("Starting multimodal document indexing...")
    result = document_loader.sync_all_documents(force=False, cleanup_missing=True)
    logger.info("Indexing complete: %s", result)
