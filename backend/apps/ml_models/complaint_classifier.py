"""
Complaint classification service using the trained DistilBERT model.
"""
import os
import logging
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
        self.local_classifier_enabled = bool(
            getattr(settings, 'ENABLE_LOCAL_CLASSIFIER', False)
        )
        self._load_models()

    def _load_models(self):
        """
        Load the trained model, tokenizer, and label encoder.
        Uses lazy loading - only loads when needed.
        """
        if not self.local_classifier_enabled:
            logger.info("Local classifier is disabled. Using lightweight fallback classifier.")
            return

        try:
            import joblib

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
            from transformers import DistilBertTokenizer
            self.tokenizer = DistilBertTokenizer.from_pretrained(self.tokenizer_path)
            logger.info("Tokenizer loaded successfully")

            # Model will be loaded in predict() to ensure thread safety
            # self.model is not stored persistently
            logger.info("Resources loaded successfully (Model will be loaded on demand)")

        except Exception as e:
            logger.error(f"Error loading models: {e}")
            logger.warning("ML models failed to load. Using fallback mode.")
            # Don't raise - allow app to continue without ML

    @staticmethod
    def _fallback_predict(complaint_text, crash=False, fire=False):
        """
        Fallback classifier when ML artifacts are unavailable.
        1) Try Cohere-based category classification.
        2) If unavailable/failed, use lightweight keyword heuristics.
        """
        raw_text = (complaint_text or "").lower()
        categories = [
            "advanced_safety",
            "airbags_seatbelts",
            "brakes_safety",
            "electrical_system",
            "engine",
            "fuel_system",
            "power_train",
            "steering_suspension",
            "structure_body",
            "visibility_lighting",
            "wheels_tires",
        ]
        provider_strategy = getattr(settings, 'LLM_PROVIDER_STRATEGY', 'cohere_first').lower()
        try:
            import json
            import re
            from .cohere_service import cohere_service

            if cohere_service.is_available and provider_strategy != 'local_first':
                prompt = (
                    "Classify this vehicle complaint into exactly one category from:\n"
                    f"{', '.join(categories)}\n\n"
                    "Return strict JSON with keys: category, confidence.\n"
                    f"Complaint: {complaint_text}\n"
                    f"Crash flag: {bool(crash)}\n"
                    f"Fire flag: {bool(fire)}"
                )
                text = cohere_service.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=120,
                )
                json_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    category = str(parsed.get("category", "")).strip()
                    confidence = float(parsed.get("confidence", 0.55))
                    if category in categories:
                        return {
                            "category": category,
                            "confidence": max(0.3, min(0.95, confidence)),
                            "all_probabilities": {category: 1.0},
                            "fallback": True,
                            "fallback_source": "cohere",
                        }
        except Exception as llm_exc:
            if '429' in str(llm_exc) or 'too many requests' in str(llm_exc).lower():
                logger.warning(
                    "Cohere fallback classification failed; fallback=keywords: %s",
                    str(llm_exc).splitlines()[0],
                )
            else:
                logger.warning("Cohere fallback classification failed: %s", llm_exc)

        keyword_map = {
            "engine": ["engine", "motor", "misfire", "rpm", "stall", "overheat", "oil"],
            "brakes_safety": ["brake", "pedal", "disc", "drum", "abs"],
            "electrical_system": ["battery", "alternator", "fuse", "wiring", "electrical", "short"],
            "fuel_system": ["fuel", "petrol", "gas", "injector", "pump"],
            "power_train": ["gear", "gearbox", "transmission", "clutch", "cvt"],
            "steering_suspension": ["steering", "suspension", "alignment", "shock", "vibration"],
            "structure_body": ["body", "chassis", "door", "hood", "trunk", "bumper", "dent", "collision"],
            "visibility_lighting": ["light", "headlight", "lamp", "wiper", "windshield", "window"],
            "wheels_tires": ["wheel", "wheels", "tire", "tyre", "rim", "puncture"],
            "airbags_seatbelts": ["airbag", "seat belt", "seatbelt"],
            "advanced_safety": ["adas", "sensor", "radar", "lane", "camera", "collision warning"],
        }

        scores = {category: 0 for category in keyword_map}
        for category, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in raw_text:
                    scores[category] += 1

        # Safety-critical flags boost related categories.
        if crash:
            scores["structure_body"] += 3
            scores["airbags_seatbelts"] += 2
            scores["brakes_safety"] += 1
        if fire:
            scores["fuel_system"] += 3
            scores["electrical_system"] += 2
            scores["engine"] += 2

        best_category, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score == 0:
            best_category = "engine"
            confidence = 0.35
        else:
            confidence = min(0.90, 0.45 + (best_score * 0.08))

        total_score = sum(scores.values())
        if total_score > 0:
            all_probabilities = {
                category: round(score / total_score, 4)
                for category, score in scores.items()
                if score > 0
            }
        else:
            all_probabilities = {best_category: 1.0}

        return {
            "category": best_category,
            "confidence": confidence,
            "all_probabilities": all_probabilities,
            "fallback": True,
            "fallback_source": "keywords",
        }

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
        if not self.local_classifier_enabled:
            return self._fallback_predict(complaint_text, crash=crash, fire=fire)

        if not self.tokenizer or not self.label_encoder:
            logger.warning("Local classifier artifacts are unavailable, using fallback classifier")
            return self._fallback_predict(complaint_text, crash=crash, fire=fire)

        try:
            import numpy as np

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
            fallback_result = self._fallback_predict(complaint_text, crash=crash, fire=fire)
            fallback_result['error'] = str(e)
            return fallback_result

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

