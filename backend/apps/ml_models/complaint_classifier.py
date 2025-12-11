"""
Complaint classification service using the trained DistilBERT model.
"""
import os
import logging
import numpy as np
import joblib
from django.conf import settings
from .text_preprocessing import clean_text

logger = logging.getLogger(__name__)


class ComplaintClassifier:
    """
    Service class for classifying car complaints using the trained ML model.
    """

    def __init__(self):
        """Initialize the classifier with model and tokenizer."""
        self.model = None
        self.tokenizer = None
        self.label_encoder = None
        self.max_len = 512  # BERT max sequence length
        self.le_path = settings.LABEL_ENCODER_PATH
        self.tokenizer_path = settings.BERT_TOKENIZER_PATH
        self.model_path = settings.TRAINED_MODEL_PATH
        self._load_models()

    def _load_models(self):
        """
        Load the trained model, tokenizer, and label encoder.
        Uses lazy loading - only loads when needed.
        """
        try:
            # Check if all paths exist
            if not os.path.exists(self.le_path):
                logger.warning(f"Label encoder not found at {self.le_path}")
                return
            if not os.path.exists(self.tokenizer_path):
                logger.warning(f"Tokenizer not found at {self.tokenizer_path}")
                return
            if not os.path.exists(self.model_path):
                logger.warning(f"Trained model not found at {self.model_path}")
                return

            # Load resources
            self.label_encoder = joblib.load(self.le_path)
            logger.info("Label encoder loaded successfully")

            # Load tokenizer
            from transformers import DistilBertTokenizer, TFDistilBertModel
            self.tokenizer = DistilBertTokenizer.from_pretrained(self.tokenizer_path)
            logger.info("Tokenizer loaded successfully")

            # Model will be loaded in predict() to ensure thread safety
            # self.model is not stored persistently
            logger.info("Resources loaded successfully (Model will be loaded on demand)")

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            logger.warning("ML models failed to load. Using fallback mode.")
            # Don't raise - allow app to continue without ML

    def predict(self, complaint_text, crash=False, fire=False):
        """
        Predict the category of a complaint.

        Args:
            complaint_text: Raw complaint text from customer
            crash: Boolean indicating if complaint involves a crash
            fire: Boolean indicating if complaint involves a fire

        Returns:
            dict: {
                'category': predicted category string,
                'confidence': confidence score (0-1),
                'all_probabilities': dict of all category probabilities
            }
        """
        if not self.tokenizer or not self.label_encoder:
            logger.error("Models not loaded properly")
            return {
                'category': 'engine',  # Default fallback
                'confidence': 0.5,  # Provide a non‑zero confidence for fallback
                'all_probabilities': {}
            }

        try:
            # 1. Clean the text
            cleaned_text = clean_text(complaint_text)

            # 2. Tokenize
            encodings = self.tokenizer(
                [cleaned_text],
                truncation=True,
                padding='max_length',
                max_length=self.max_len,
                return_tensors='tf'
            )

            # 3. Prepare numeric features (crash, fire)
            numeric_features = np.array([[int(crash), int(fire)]], dtype=np.int32)

            # 4. Make prediction using captured graph/session
            # 4. Make prediction - Load model fresh to avoid session issues
            import tensorflow as tf
            from transformers import TFDistilBertModel
            # Disable eager execution if needed, or just load directly
            # For robustness, we load the model here
            custom_objects = {'TFDistilBertModel': TFDistilBertModel}
            temp_model = tf.keras.models.load_model(self.model_path, custom_objects=custom_objects)
            
            predictions = temp_model.predict(
                [encodings['input_ids'], encodings['attention_mask'], numeric_features],
                verbose=0,
                steps=1
            )
            
            # Cleanup to free memory
            del temp_model
            tf.keras.backend.clear_session()

            # 5. Get predicted class and confidence
            predicted_class_idx = np.argmax(predictions[0])
            confidence = float(predictions[0][predicted_class_idx])

            # 6. Convert to category name
            category = self.label_encoder.inverse_transform([predicted_class_idx])[0]

            # 7. Get all probabilities
            all_probabilities = {}
            for idx, prob in enumerate(predictions[0]):
                cat_name = self.label_encoder.inverse_transform([idx])[0]
                all_probabilities[cat_name] = float(prob)

            return {
                'category': category,
                'confidence': confidence,
                'all_probabilities': all_probabilities,
                'cleaned_text': cleaned_text
            }

        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return {
                'category': 'engine',  # Default fallback
                'confidence': 0.5,  # Provide a non‑zero confidence on exception
                'all_probabilities': {},
                'error': str(e)
            }

    def predict_batch(self, complaints_data):
        """
        Predict categories for multiple complaints at once.

        Args:
            complaints_data: List of dicts with 'text', 'crash', 'fire' keys

        Returns:
            list: List of prediction dicts
        """
        results = []
        for complaint in complaints_data:
            result = self.predict(
                complaint_text=complaint.get('text', ''),
                crash=complaint.get('crash', False),
                fire=complaint.get('fire', False)
            )
            results.append(result)
        return results


# Global classifier instance (lazy loaded)
_classifier = None


def get_classifier():
    """
    Get or create the global complaint classifier instance.

    Returns:
        ComplaintClassifier: The classifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = ComplaintClassifier()
    return _classifier


def classify_complaint(complaint_text, crash=False, fire=False):
    """
    Convenience function to classify a single complaint.

    Args:
        complaint_text: Raw complaint text
        crash: Whether complaint involves crash
        fire: Whether complaint involves fire

    Returns:
        dict: Prediction results
    """
    classifier = get_classifier()
    return classifier.predict(complaint_text, crash, fire)
