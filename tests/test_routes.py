import io
import pytest
from unittest.mock import patch, MagicMock
from app import db, User

def test_home_page(client):
    """Test the home page loads."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Light" in response.data
    assert b"AI" in response.data

def test_login_page(client):
    """Test the login page loads."""
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Login" in response.data

def test_register_page(client):
    """Test the register page loads."""
    response = client.get('/register')
    assert response.status_code == 200
    assert b"Sign Up" in response.data

def test_dashboard_access_unauthorized(client):
    """Test that dashboard requires login."""
    response = client.get('/dashboard')
    assert response.status_code == 302  # Redirect to login

def test_dashboard_access_authorized(auth_client):
    """Test that dashboard loads for logged-in user."""
    response = auth_client.get('/dashboard')
    assert response.status_code == 200
    assert b"New Grading Session" in response.data

@patch('app.extract_text_from_file')
@patch('app.analyze_answer_with_ai')
def test_upload_route_success(mock_analyze, mock_extract, auth_client):
    """
    Test the upload route with mocked AI and Text Extraction.
    This avoids calling real Gemini/Groq APIs and Tesseract OCR.
    """
    # Mock the text extraction to return dummy text
    mock_extract.return_value = "This is the extracted text content."

    # Mock the AI analysis to return a fixed score
    mock_analyze.return_value = {
        'score': 8.5,
        'feedback': 'Good job!',
        'suggestions': 'Add more details.'
    }

    # Create dummy files for upload
    data = {
        'question_file': (io.BytesIO(b"Question content"), 'question.txt'),
        'answer_files': [(io.BytesIO(b"Answer content"), 'student_answer.txt')]
    }

    response = auth_client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)

    # Check that the response is successful (200 OK)
    assert response.status_code == 200
    
    # Check that our mocked results appear in the output
    assert b"Evaluation Results" in response.data
    assert b"8.5" in response.data
    assert b"Good job!" in response.data

@patch('app.pytesseract.image_to_string')
@patch('PIL.Image.open')
def test_ocr_mocking(mock_image_open, mock_tesseract):
    """
    Test the OCR function specifically by mocking Tesseract.
    """
    from app import extract_text_from_image
    
    # Mock Image.open to return a dummy image object
    mock_image = MagicMock()
    mock_image_open.return_value = mock_image
    
    # Mock Tesseract to return specific text
    mock_tesseract.return_value = "Mocked OCR Text"
    
    # Call the function
    result = extract_text_from_image("dummy_path.png")
    
    # Assertions
    assert result == "Mocked OCR Text"
    mock_tesseract.assert_called()

@patch('app.model')
def test_gemini_ai_mocking(mock_model):
    """
    Test the AI analysis function by mocking the Gemini model.
    """
    from app import analyze_answer_with_ai
    
    # Setup the mock response structure for Gemini
    mock_response = MagicMock()
    mock_response.text = """
    SCORE: 9.0
    FEEDBACK: Excellent answer.
    SUGGESTIONS: None.
    """
    mock_model.generate_content.return_value = mock_response
    
    # Call the function
    result = analyze_answer_with_ai("Question", "Answer", "Student Answer")
    
    # Assertions
    assert result['score'] == 9.0
    assert "Excellent answer" in result['feedback']
