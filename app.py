import os
import io
import uuid
from flask import Flask, request, render_template, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import pytesseract
import PyPDF2
import pandas as pd
import spacy
from datetime import datetime
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure upload folders
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload and results folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Configure Gemini AI
api_key = os.getenv('GEMINI_API_KEY')
if api_key and api_key != 'your_gemini_api_key_here':
    try:
        genai.configure(api_key=api_key)
        # Use the latest working model
        model = genai.GenerativeModel('gemini-1.5-flash')
        vision_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini AI configured successfully with gemini-1.5-flash")
    except Exception as e:
        print(f"❌ Gemini AI configuration failed: {e}")
        print("💡 Please check your API key in .env file")
        model = None
        vision_model = None
else:
    print("⚠️  Gemini API key not set - using fallback NLP scoring")
    print("💡 Add your API key to .env file for AI-powered evaluation")
    model = None
    vision_model = None

# Configure Tesseract OCR
try:
    # Set Tesseract path for Windows
    if os.name == 'nt':  # Windows
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"✅ Tesseract found at: {path}")
                break
        else:
            print("⚠️  Tesseract not found in common paths. OCR may not work for images.")
    
    # Test Tesseract
    test_result = pytesseract.get_tesseract_version()
    print(f"✅ Tesseract version: {test_result}")
except Exception as e:
    print(f"Warning: Tesseract OCR configuration failed: {e}")

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Warning: spaCy model 'en_core_web_sm' not found. Please install it with: python -m spacy download en_core_web_sm")
    nlp = None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_image(image_path):
    """Extract text from image using OCR with enhanced handwriting support"""
    try:
        image = Image.open(image_path)
        
        # Try multiple OCR configurations for better handwriting recognition
        configs = [
            '--psm 6',  # Uniform block of text (default)
            '--psm 4',  # Single column of text
            '--psm 8',  # Single word
            '--psm 13', # Raw line without heuristics (good for handwriting)
        ]
        
        best_text = ""
        best_confidence = 0
        
        for config in configs:
            try:
                # Extract text with current configuration
                text = pytesseract.image_to_string(image, config=config)
                
                # Get confidence score
                data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # Keep the best result
                if avg_confidence > best_confidence and len(text.strip()) > len(best_text.strip()):
                    best_text = text
                    best_confidence = avg_confidence
                    
            except Exception as config_error:
                continue
        
        # If no good result, try standard extraction
        if not best_text.strip():
            best_text = pytesseract.image_to_string(image)
            
        print(f"OCR confidence: {best_confidence:.1f}%")
        return best_text
        
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

def extract_text_from_file(file_path):
    """Extract text from various file types"""
    file_extension = file_path.rsplit('.', 1)[1].lower()
    
    if file_extension == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension in ['png', 'jpg', 'jpeg', 'gif']:
        return extract_text_from_image(file_path)
    elif file_extension == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return ""

def analyze_answer_with_gemini(question, correct_answer, student_answer):
    """Analyze student answer using Gemini AI"""
    if not model:
        return {
            'score': 0,
            'feedback': 'AI model not available',
            'details': 'Gemini AI is not properly configured'
        }
    
    try:
        prompt = f"""
        As an expert teacher, evaluate the following student answer:
        
        Question: {question}
        
        Correct Answer: {correct_answer}
        
        Student Answer: {student_answer}
        
        Please provide:
        1. A score out of 10
        2. Detailed feedback explaining what's correct and what's missing
        3. Suggestions for improvement
        
        Format your response as JSON with keys: score, feedback, suggestions
        """
        
        response = model.generate_content(prompt)
        
        # Try to parse JSON from response
        try:
            result = json.loads(response.text)
            return {
                'score': result.get('score', 0),
                'feedback': result.get('feedback', 'No feedback available'),
                'suggestions': result.get('suggestions', 'No suggestions available')
            }
        except json.JSONDecodeError:
            # If JSON parsing fails, extract information from text
            text = response.text
            score_match = re.search(r'score.*?(\d+)', text, re.IGNORECASE)
            score = int(score_match.group(1)) if score_match else 5
            
            return {
                'score': score,
                'feedback': text,
                'suggestions': 'Review the feedback above for improvement suggestions'
            }
    except Exception as e:
        return {
            'score': 0,
            'feedback': f'Error in AI evaluation: {str(e)}',
            'suggestions': 'Please try again or contact support'
        }

def simple_answer_comparison(question, correct_answer, student_answer):
    """Simple keyword-based answer comparison when AI is not available"""
    if not nlp:
        # Basic string matching fallback
        correct_words = set(correct_answer.lower().split())
        student_words = set(student_answer.lower().split())
        overlap = len(correct_words.intersection(student_words))
        score = min(10, (overlap / len(correct_words)) * 10) if correct_words else 0
        
        return {
            'score': round(score, 1),
            'feedback': f'Basic comparison: {overlap} key terms matched out of {len(correct_words)}',
            'suggestions': 'Include more key terms from the correct answer'
        }
    
    # Use spaCy for better comparison
    correct_doc = nlp(correct_answer)
    student_doc = nlp(student_answer)
    
    similarity = correct_doc.similarity(student_doc)
    score = similarity * 10
    
    return {
        'score': round(score, 1),
        'feedback': f'Semantic similarity: {similarity:.2f}. Answer shows {"good" if similarity > 0.7 else "moderate" if similarity > 0.4 else "poor"} understanding.',
        'suggestions': 'Try to include more relevant concepts and use similar terminology as the correct answer'
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        # Check if files were uploaded
        if 'question_file' not in request.files or 'answer_files' not in request.files:
            flash('Missing required files')
            return redirect(url_for('index'))
        
        question_file = request.files['question_file']
        answer_files = request.files.getlist('answer_files')
        
        if question_file.filename == '':
            flash('No question file selected')
            return redirect(url_for('index'))
        
        if not answer_files or all(f.filename == '' for f in answer_files):
            flash('No answer files selected')
            return redirect(url_for('index'))
        
        # Create unique session folder
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        results = {'session_id': session_id, 'evaluations': []}
        
        # Process question file
        if question_file and allowed_file(question_file.filename):
            question_filename = secure_filename(question_file.filename)
            question_path = os.path.join(session_folder, 'question_' + question_filename)
            question_file.save(question_path)
            
            question_text = extract_text_from_file(question_path)
            if not question_text.strip():
                flash('Could not extract text from question file')
                return redirect(url_for('index'))
        else:
            flash('Invalid question file format')
            return redirect(url_for('index'))
        
        # Process answer files
        for i, answer_file in enumerate(answer_files):
            if answer_file and allowed_file(answer_file.filename):
                answer_filename = secure_filename(answer_file.filename)
                answer_path = os.path.join(session_folder, f'answer_{i}_{answer_filename}')
                answer_file.save(answer_path)
                
                student_answer = extract_text_from_file(answer_path)
                
                # For demo purposes, we'll treat the question text as both question and answer
                # In a real scenario, you'd separate questions and answers
                if model:
                    evaluation = analyze_answer_with_gemini(question_text, question_text, student_answer)
                else:
                    evaluation = simple_answer_comparison(question_text, question_text, student_answer)
                
                results['evaluations'].append({
                    'student_file': answer_filename,
                    'student_answer': student_answer[:500] + '...' if len(student_answer) > 500 else student_answer,
                    'score': evaluation['score'],
                    'feedback': evaluation['feedback'],
                    'suggestions': evaluation.get('suggestions', '')
                })
        
        # Generate Excel report
        excel_path = generate_excel_report(results, session_id)
        
        return render_template('results.html', 
                             results=results, 
                             excel_path=excel_path,
                             session_id=session_id)
        
    except Exception as e:
        flash(f'Error processing files: {str(e)}')
        return redirect(url_for('index'))

def generate_excel_report(results, session_id):
    """Generate Excel report with evaluation results"""
    df_data = []
    
    for i, eval_result in enumerate(results['evaluations']):
        df_data.append({
            'Student': f'Student {i+1}',
            'File Name': eval_result['student_file'],
            'Score': eval_result['score'],
            'Feedback': eval_result['feedback'],
            'Suggestions': eval_result['suggestions']
        })
    
    df = pd.DataFrame(df_data)
    
    excel_filename = f'evaluation_report_{session_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    excel_path = os.path.join(RESULTS_FOLDER, excel_filename)
    
    df.to_excel(excel_path, index=False, engine='openpyxl')
    
    return excel_filename

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated Excel report"""
    try:
        file_path = os.path.join(RESULTS_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            flash('File not found')
            return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'gemini_configured': model is not None,
        'spacy_loaded': nlp is not None,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting AI Assignment Checker...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Results folder: {RESULTS_FOLDER}")
    print(f"Gemini AI configured: {model is not None}")
    print(f"spaCy loaded: {nlp is not None}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)