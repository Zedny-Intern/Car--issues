from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class MlModelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ml_models'
    verbose_name = 'ML Models & Multi-modal RAG'
    
    def ready(self):
        """
        Called when Django starts. Optionally trigger document indexing.
        Note: We don't auto-index on every startup to avoid slow boots.
        Use the API endpoint or Celery task to trigger indexing manually.
        """
        # Import signals or register tasks here if needed
        pass
        
        # Uncomment below to auto-index on startup (may slow boot):
        # import threading
        # def delayed_index():
        #     import time
        #     time.sleep(10)  # Wait for app to fully start
        #     try:
        #         from .document_loader import startup_index_documents
        #         startup_index_documents()
        #     except Exception as e:
        #         logger.error(f"Startup indexing failed: {e}")
        # 
        # threading.Thread(target=delayed_index, daemon=True).start()

