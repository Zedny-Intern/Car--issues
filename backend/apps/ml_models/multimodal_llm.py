"""
LLM integration using LangChain with Ollama.
Text-only version.
"""
import logging
from typing import List, Dict, Optional, Generator

from django.conf import settings

logger = logging.getLogger(__name__)

# LangChain imports
try:
    from langchain_community.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGCHAIN_OLLAMA_AVAILABLE = True
except ImportError:
    ChatOllama = None
    LANGCHAIN_OLLAMA_AVAILABLE = False
    logger.warning("langchain-community not installed for Ollama support")


class MultimodalLLM:
    """
    LLM service using LangChain with Ollama.
    Named 'MultimodalLLM' for legacy compatibility, but now Text-Only.
    """
    
    def __init__(self):
        """Initialize the LLM service."""
        # Use configurable base URL from settings (host.docker.internal for Docker containers)
        self.ollama_base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
        self.text_model = getattr(settings, 'OLLAMA_TEXT_MODEL', 'llama3')
        
        # LangChain model instances (lazy loaded)
        self._text_llm = None
        
        # Cache availability check
        self._ollama_available = None
    
    @property
    def text_llm(self):
        """Lazy load text model via LangChain."""
        if self._text_llm is None and LANGCHAIN_OLLAMA_AVAILABLE:
            try:
                self._text_llm = ChatOllama(
                    model=self.text_model,
                    base_url=self.ollama_base_url,
                    temperature=0.7
                )
                logger.info(f"Initialized LangChain ChatOllama with {self.text_model}")
            except Exception as e:
                logger.error(f"Failed to initialize text model: {e}")
        return self._text_llm
    
    def check_ollama_available(self) -> bool:
        """Check if Ollama server is running."""
        if self._ollama_available is not None:
            return self._ollama_available
        
        try:
            import requests
            response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            self._ollama_available = response.status_code == 200
            return self._ollama_available
        except:
            self._ollama_available = False
            return False
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate a response using LangChain ChatOllama.
        """
        if not LANGCHAIN_OLLAMA_AVAILABLE:
            return "⚠️ LangChain Ollama not available. Install with: pip install langchain-community"
        
        if not self.check_ollama_available():
            return "⚠️ Ollama server not running. Start with: ollama serve"
        
        try:
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            
            # Text-only message
            messages.append(HumanMessage(content=prompt))
            
            # Use text model
            llm = self.text_llm
            if llm is None:
                return "⚠️ No LLM model available"
            response = llm.invoke(messages)
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"
    
    def generate_stream(self, prompt: str, system_prompt: str = None) -> Generator[str, None, None]:
        """
        Stream a response using LangChain ChatOllama.
        """
        if not LANGCHAIN_OLLAMA_AVAILABLE or not self.check_ollama_available():
            yield "⚠️ Ollama not available"
            return
        
        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            llm = self.text_llm
            if llm is None:
                yield "⚠️ No LLM model available"
                return
            
            for chunk in llm.stream(messages):
                if chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def answer_with_context(self, question: str, text_context: str) -> str:
        """
        Answer using RAG context.
        """
        system_prompt = """You are an expert car mechanic assistant with access to official car service manuals. 
Use the provided context to give accurate, detailed answers.
If the context doesn't contain the answer, say so clearly.
Reference specific parts or page numbers when relevant."""
        
        full_prompt = f"""## Context from Car Service Manuals:
{text_context}

## User Question:
{question}

Please provide a helpful, accurate answer based on the context above."""
        
        return self.generate(full_prompt, system_prompt=system_prompt)
    
    # Deprecated methods
    def describe_image(self, image_path: str, question: str = None) -> str:
        return "Image analysis is no longer supported."

    def get_status(self) -> Dict:
        """Get service status."""
        import requests
        
        available_models = []
        if self.check_ollama_available():
            try:
                response = requests.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    available_models = [m.get('name') for m in response.json().get('models', [])]
            except:
                pass
        
        return {
            'langchain_available': LANGCHAIN_OLLAMA_AVAILABLE,
            'ollama_available': self.check_ollama_available(),
            'ollama_url': self.ollama_base_url,
            'text_model': self.text_model,
            'available_models': available_models,
            'text_initialized': self._text_llm is not None
        }


# Global instance
multimodal_llm = MultimodalLLM()
