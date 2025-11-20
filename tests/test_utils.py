import pytest
from app import allowed_file, simple_answer_comparison

def test_allowed_file():
    """Test the allowed_file utility function."""
    assert allowed_file('document.pdf') is True
    assert allowed_file('image.png') is True
    assert allowed_file('photo.jpg') is True
    assert allowed_file('notes.txt') is True
    assert allowed_file('script.exe') is False
    assert allowed_file('data.csv') is False
    assert allowed_file('no_extension') is False

def test_simple_answer_comparison_logic():
    """Test the fallback comparison logic when AI is not available."""
    question = "What is the capital of France?"
    correct = "The capital of France is Paris."
    
    # Test exact match (or close to it)
    student_good = "Paris is the capital of France."
    result_good = simple_answer_comparison(question, correct, student_good)
    assert result_good['score'] > 5
    
    # Test poor match
    student_bad = "The sky is blue."
    result_bad = simple_answer_comparison(question, correct, student_bad)
    
    # Ensure good answer scores higher than bad answer
    # Note: With small spacy models, similarity can be tricky, so we check for a reasonable difference
    # or just that the good score is decent.
    assert result_good['score'] > result_bad['score']

    # Test empty
    result_empty = simple_answer_comparison(question, correct, "")
    assert result_empty['score'] == 0
