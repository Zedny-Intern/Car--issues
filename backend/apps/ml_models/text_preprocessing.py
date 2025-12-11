"""
Text preprocessing utilities for complaint classification.
"""
import re
import string


def clean_text(text):
    """
    Clean and preprocess complaint text for ML classification.
    
    Args:
        text (str): Raw complaint text
        
    Returns:
        str: Cleaned text ready for tokenization
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove URLs
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)
    
    # Remove special characters and digits (keep spaces and basic punctuation)
    # Keep some punctuation that might be meaningful (.,!?)
    text = re.sub(r'[^a-z\s.,!?]', ' ', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def remove_stopwords(text, stopwords=None):
    """
    Remove common stopwords from text.
    
    Args:
        text (str): Input text
        stopwords (set): Set of stopwords to remove (optional)
        
    Returns:
        str: Text with stopwords removed
    """
    if stopwords is None:
        # Common English stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'my', 'your', 'his', 'her', 'its', 'our', 'their'
        }
    
    words = text.split()
    filtered_words = [word for word in words if word not in stopwords]
    return ' '.join(filtered_words)


def preprocess_for_bert(text, remove_stops=False):
    """
    Full preprocessing pipeline for BERT-based models.
    
    Args:
        text (str): Raw input text
        remove_stops (bool): Whether to remove stopwords (default: False)
        
    Returns:
        str: Preprocessed text
    """
    # Clean text
    text = clean_text(text)
    
    # Optionally remove stopwords (generally not needed for BERT)
    if remove_stops:
        text = remove_stopwords(text)
    
    return text
