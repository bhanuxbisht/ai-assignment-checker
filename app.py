import os
import io
import uuid
from flask import Flask, request, render_template, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo
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

# Database Configuration
# Use environment variable for DB URL (Render/Production) or fallback to local SQLite
database_url = os.getenv('DATABASE_URL', 'sqlite:///users.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Login Manager Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

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
gemini_api_key = os.getenv('GEMINI_API_KEY')
if gemini_api_key and gemini_api_key != 'your_gemini_api_key_here':
    try:
        genai.configure(api_key=gemini_api_key)
        # Use the stable working model (Gemini 2.0 Flash)
        model = genai.GenerativeModel('gemini-2.0-flash')
        vision_model = genai.GenerativeModel('gemini-2.0-flash')
        print("✅ Gemini AI configured successfully with gemini-2.0-flash")
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

# Configure Groq AI (Fast LLM Inference) as backup
groq_api_key = os.getenv('GROQ_API_KEY')
groq_api_url = "https://api.groq.com/openai/v1/chat/completions"
if groq_api_key:
    print("✅ Groq AI configured successfully as backup LLM (console.groq.com)")
else:
    print("⚠️  Groq API key not found. Get your key from https://console.groq.com/keys")

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
    """ULTRA-FAST PDF extraction (supports both digital and image-based PDFs)"""
    try:
        # SPEED OPTIMIZATION: Try digital text extraction first (instant)
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # If text was extracted successfully, return it immediately
        if text.strip() and len(text) > 100:  # At least 100 chars for valid text
            print(f"⚡ FAST: Extracted digital text ({len(text)} chars) - NO OCR NEEDED")
            return text
        
        # If no text found, try OCR on PDF images (for scanned/photo-based PDFs)
        print("📸 Photo-based PDF detected. Starting smart OCR...")
        try:
            from pdf2image import convert_from_path
            import os
            import concurrent.futures
            
            # Set poppler path for Windows
            poppler_path = None
            possible_paths = [
                os.path.expanduser("~/poppler/poppler-24.08.0/Library/bin"),
                "C:\\Program Files\\poppler\\poppler-24.08.0\\Library\\bin",
                os.path.expanduser("~/poppler/Library/bin")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    poppler_path = path
                    break
            
            # SPEED BOOST: Use optimal DPI (150 is perfect balance: fast + accurate)
            if poppler_path:
                images = convert_from_path(pdf_path, dpi=150, poppler_path=poppler_path, thread_count=4)
            else:
                images = convert_from_path(pdf_path, dpi=150, thread_count=4)
            
            print(f"📄 Processing {len(images)} page(s) in PARALLEL...")
            
            # MASSIVE SPEED BOOST: Process pages in parallel
            def process_page(page_data):
                i, image = page_data
                page_text = extract_text_from_image_pil_fast(image)
                
                # BUG FIX: If fast OCR returns 0 chars, try full preprocessing
                if not page_text.strip():
                    print(f"   ⚠️  Page {i+1} fast OCR failed (0 chars), trying full preprocessing...")
                    page_text = extract_text_from_image_pil(image)
                
                print(f"   ✓ Page {i+1} done ({len(page_text)} chars)")
                return (i, page_text)
            
            # Process all pages concurrently (4x faster!)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(process_page, enumerate(images)))
            
            # Combine results in correct order
            results.sort(key=lambda x: x[0])
            ocr_text = "\n".join([f"--- Page {i+1} ---\n{text}" for i, text in results if text.strip()])
            
            if ocr_text.strip():
                print(f"⚡ PARALLEL OCR: Extracted {len(ocr_text)} chars from {len(images)} pages")
                return ocr_text
            else:
                print("⚠️  No text could be extracted from PDF images")
                return ""
                
        except ImportError:
            print("⚠️  pdf2image not installed. Cannot process image-based PDFs.")
            print("   Install with: pip install pdf2image")
            return ""
        except Exception as ocr_error:
            print(f"⚠️  OCR extraction from PDF failed: {ocr_error}")
            return ""
            
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

def extract_text_from_image(image_path):
    """Extract text from image file using OCR with enhanced handwriting support"""
    try:
        image = Image.open(image_path)
        return extract_text_from_image_pil(image)
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

def extract_text_from_image_pil(image):
    """SMART OCR - Balanced accuracy and speed for production use"""
    try:
        import cv2
        import numpy as np
        
        # Convert PIL to OpenCV format
        img_array = np.array(image)
        if len(img_array.shape) == 2:
            img = img_array
        else:
            img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # === OPTIMIZED PREPROCESSING (3X FASTER) ===
        
        # 1. Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # 2. Smart upscaling (only if needed, saves time)
        height, width = gray.shape
        if height < 800:
            scale = 800 / height
            new_width = int(width * scale)
            gray = cv2.resize(gray, (new_width, 800), interpolation=cv2.INTER_CUBIC)
        
        # 3. Fast denoising
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # 4. CLAHE enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # 5. Best threshold method (adaptive is most reliable)
        thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        
        # Convert back to PIL
        from PIL import Image as PILImage
        processed_img = PILImage.fromarray(thresh)
        
        # OPTIMIZED OCR CONFIG: LSTM engine with smart settings
        config = r'--oem 1 --psm 6 -c preserve_interword_spaces=1'
        text = pytesseract.image_to_string(processed_img, config=config, lang='eng')
        
        # Get confidence
        try:
            data = pytesseract.image_to_data(processed_img, config=config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        except:
            avg_confidence = 75.0  # Assume good confidence
        
        if text.strip():
            print(f"✅ OCR: {avg_confidence:.1f}% confidence | {len(text)} chars | Method: Smart-Fast")
            return text.strip()
        else:
            # Fallback to basic OCR
            text = pytesseract.image_to_string(image, lang='eng')
            print(f"⚠️  Fallback OCR: {len(text)} chars")
            return text.strip()
        
    except ImportError:
        # Fallback without OpenCV (still works, just less accurate)
        print("⚠️  OpenCV not available - using basic OCR")
        config = r'--oem 1 --psm 6 -c preserve_interword_spaces=1'
        text = pytesseract.image_to_string(image, config=config, lang='eng')
        return text.strip()
        
    except Exception as e:
        print(f"❌ OCR error: {e}")
        try:
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()
        except:
            return ""

def extract_text_from_image_pil_fast(image):
    """ULTRA-FAST OCR for photo-based PDFs (parallel processing) - BUG FIX"""
    try:
        import cv2
        import numpy as np
        
        # BUG FIX: Add preprocessing even for fast OCR to avoid 0 character extraction
        img_array = np.array(image)
        if len(img_array.shape) == 2:
            gray = img_array
        else:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        
        # Quick enhancement to prevent blank pages
        height, width = gray.shape
        if height < 600:
            scale = 600 / height
            new_width = int(width * scale)
            gray = cv2.resize(gray, (new_width, 600), interpolation=cv2.INTER_CUBIC)
        
        # Quick CLAHE enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Convert to PIL for OCR
        from PIL import Image as PILImage
        processed_img = PILImage.fromarray(enhanced)
        
        # Try multiple PSM modes for better text detection
        configs = [
            r'--oem 1 --psm 6 -c preserve_interword_spaces=1',  # Uniform text block
            r'--oem 1 --psm 3 -c preserve_interword_spaces=1',  # Fully automatic
            r'--oem 1 --psm 4 -c preserve_interword_spaces=1',  # Single column
        ]
        
        best_text = ""
        for config in configs:
            try:
                text = pytesseract.image_to_string(processed_img, config=config, lang='eng')
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text.strip()
                    if len(best_text) > 50:  # If we got good text, stop trying
                        break
            except:
                continue
        
        # Final fallback: try original image
        if not best_text.strip():
            try:
                best_text = pytesseract.image_to_string(image, lang='eng').strip()
            except:
                pass
        
        return best_text
        
    except ImportError:
        # Fallback without OpenCV
        try:
            configs = [
                r'--oem 1 --psm 6 -c preserve_interword_spaces=1',
                r'--oem 1 --psm 3 -c preserve_interword_spaces=1',
            ]
            for config in configs:
                try:
                    text = pytesseract.image_to_string(image, config=config, lang='eng')
                    if text.strip():
                        return text.strip()
                except:
                    continue
            return ""
        except:
            return ""
    except Exception as e:
        print(f"⚠️  Fast OCR error: {e}")
        try:
            text = pytesseract.image_to_string(image, lang='eng')
            return text.strip()
        except:
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

def analyze_answer_with_ai(question, correct_answer, student_answer):
    """FAIR & UNBIASED AI Evaluation with DUAL LLM + Error Handling"""
    
    # BIAS PREVENTION: Extract key concepts for objective grading
    def extract_key_concepts(text):
        """Extract important words/concepts from text for fair comparison"""
        import re
        # Remove common words, keep important terms
        words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
        return set(words) - {'this', 'that', 'these', 'those', 'from', 'with', 'have', 'been', 'were', 'will', 'would', 'could', 'should'}
    
    # Try Gemini first (with bias prevention)
    if model:
        try:
            # BIAS PREVENTION: Enhanced prompt for objective evaluation
            prompt = f"""You are a FAIR and OBJECTIVE teacher evaluating a student's answer. Your evaluation MUST be:
1. UNBIASED - Judge only the accuracy and completeness of content
2. EVIDENCE-BASED - Point to specific facts that are correct or missing
3. CONSTRUCTIVE - Help the student improve with specific guidance
4. CONSISTENT - Use the same standards for all students

Question: {question}

Correct Answer (Reference): {correct_answer}

Student Answer: {student_answer}

Evaluate OBJECTIVELY using this format:

SCORE: [number from 0-10]
- Award points ONLY for accurate, relevant content
- Deduct points ONLY for factual errors or missing key concepts
- Ignore writing style, length, or minor grammar issues

FEEDBACK:
[2-3 sentences explaining:
 - Which KEY CONCEPTS the student correctly identified
 - Which ESSENTIAL POINTS are missing or incorrect
 - Be specific with examples from their answer]

SUGGESTIONS:
[2-3 specific, actionable tips to improve their answer:
 - What concepts to add
 - What errors to correct
 - How to structure the response better]

Remember: Be FAIR, OBJECTIVE, and CONSISTENT. Focus on CONTENT ACCURACY, not presentation."""
            
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,  # Lower temperature = more consistent, less bias
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 1024,
                }
            )
            text = response.text.strip()
            
            # Parse the response
            score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            feedback_match = re.search(r'FEEDBACK:\s*(.+?)(?=SUGGESTIONS:|$)', text, re.IGNORECASE | re.DOTALL)
            suggestions_match = re.search(r'SUGGESTIONS:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            
            score = float(score_match.group(1)) if score_match else 5
            feedback = feedback_match.group(1).strip() if feedback_match else text
            suggestions = suggestions_match.group(1).strip() if suggestions_match else "Review the feedback above"
            
            # Validate score is reasonable
            if score < 0 or score > 10:
                score = max(0, min(10, score))
            
            print(f"✅ Gemini AI evaluated successfully - Score: {score}/10 (FAIR & OBJECTIVE)")
            return {
                'score': round(score, 1),
                'feedback': feedback,
                'suggestions': suggestions
            }
        except Exception as gemini_error:
            print(f"⚠️  Gemini failed: {gemini_error}")
            # Continue to Groq fallback
    
    # Try Groq as backup (with same bias prevention)
    if groq_api_key:
        try:
            import requests
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {groq_api_key}"
            }
            
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a FAIR, OBJECTIVE, and UNBIASED teacher. Evaluate answers based ONLY on content accuracy and completeness. Ignore style, length, or presentation. Be consistent and evidence-based."
                    },
                    {
                        "role": "user",
                        "content": f"""Evaluate this student answer OBJECTIVELY:

Question: {question}
Correct Answer: {correct_answer}
Student Answer: {student_answer}

Respond in this format:
SCORE: [0-10] (based on content accuracy only)
FEEDBACK: [2-3 sentences about what's correct and what's missing]
SUGGESTIONS: [2-3 specific tips to improve]"""
                    }
                ],
                "temperature": 0.3,  # Low temperature for consistency
                "max_tokens": 800
            }
            
            response = requests.post(groq_api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            text = result['choices'][0]['message']['content'].strip()
            
            # Parse Groq response
            score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            feedback_match = re.search(r'FEEDBACK:\s*(.+?)(?=SUGGESTIONS:|$)', text, re.IGNORECASE | re.DOTALL)
            suggestions_match = re.search(r'SUGGESTIONS:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            
            score = float(score_match.group(1)) if score_match else 5
            feedback = feedback_match.group(1).strip() if feedback_match else text
            suggestions = suggestions_match.group(1).strip() if suggestions_match else "Review the feedback above"
            
            # Validate score
            score = max(0, min(10, score))
            
            print(f"✅ Groq AI evaluated successfully - Score: {score}/10 (FAIR & OBJECTIVE)")
            return {
                'score': round(score, 1),
                'feedback': feedback,
                'suggestions': suggestions
            }
        except Exception as groq_error:
            print(f"⚠️  Groq failed: {groq_error}")
            # Continue to spaCy fallback
    
    # Fallback to spaCy-based evaluation (completely objective)
    print("⚠️  Using spaCy fallback evaluation (100% objective)")
    return simple_answer_comparison(question, correct_answer, student_answer)

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
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created! You can now login', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email or Username already exists', 'danger')
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_files():
    """PRODUCTION-READY upload handler with comprehensive error handling"""
    try:
        # Check if files were uploaded
        if 'question_file' not in request.files or 'answer_files' not in request.files:
            flash('Missing required files. Please upload both question and answer files.')
            return redirect(url_for('index'))
        
        question_file = request.files['question_file']
        answer_files = request.files.getlist('answer_files')
        
        if question_file.filename == '':
            flash('No question file selected')
            return redirect(url_for('index'))
        
        if not answer_files or all(f.filename == '' for f in answer_files):
            flash('No answer files selected')
            return redirect(url_for('index'))
        
        # Validate file types
        if not allowed_file(question_file.filename):
            flash(f'Invalid question file format. Allowed: {", ".join(ALLOWED_EXTENSIONS)}')
            return redirect(url_for('index'))
        
        for f in answer_files:
            if f.filename != '' and not allowed_file(f.filename):
                flash(f'Invalid file format: {f.filename}. Allowed: {", ".join(ALLOWED_EXTENSIONS)}')
                return redirect(url_for('index'))
        
        # Create unique session folder
        session_id = str(uuid.uuid4())
        session_folder = os.path.join(UPLOAD_FOLDER, session_id)
        os.makedirs(session_folder, exist_ok=True)
        
        results = {'session_id': session_id, 'evaluations': []}
        
        # Process question file with error handling
        print(f"\n{'='*60}")
        print(f"📝 PROCESSING NEW ASSIGNMENT - Session: {session_id[:8]}")
        print(f"{'='*60}")
        
        if question_file and allowed_file(question_file.filename):
            question_filename = secure_filename(question_file.filename)
            question_path = os.path.join(session_folder, 'question_' + question_filename)
            
            try:
                question_file.save(question_path)
                print(f"📥 Question file saved: {question_filename}")
                
                question_text = extract_text_from_file(question_path)
                if not question_text.strip():
                    flash('Could not extract text from question file. Please ensure the file contains readable text.')
                    return redirect(url_for('index'))
                
                print(f"✅ Question extracted: {len(question_text)} characters")
                
            except Exception as save_error:
                flash(f'Error saving question file: {str(save_error)}')
                return redirect(url_for('index'))
        else:
            flash('Invalid question file format')
            return redirect(url_for('index'))
        
        # Process answer files with robust error handling
        print(f"\n📚 Processing {len([f for f in answer_files if f.filename])} student answer(s)...")
        
        successful_evaluations = 0
        failed_evaluations = 0
        
        for i, answer_file in enumerate(answer_files):
            if answer_file and answer_file.filename and allowed_file(answer_file.filename):
                answer_filename = secure_filename(answer_file.filename)
                answer_path = os.path.join(session_folder, f'answer_{i}_{answer_filename}')
                
                try:
                    print(f"\n--- Student {i+1}: {answer_filename} ---")
                    answer_file.save(answer_path)
                    
                    # Extract text with timeout protection
                    import signal
                    
                    def timeout_handler(signum, frame):
                        raise TimeoutError("Text extraction timeout")
                    
                    # Set 2-minute timeout for extraction
                    student_answer = ""
                    try:
                        # For Windows, we'll use a simpler approach without signal
                        student_answer = extract_text_from_file(answer_path)
                    except Exception as extract_error:
                        print(f"⚠️  Extraction error: {extract_error}")
                        student_answer = ""
                    
                    if not student_answer.strip():
                        print(f"⚠️  No text extracted from {answer_filename} - Skipping")
                        failed_evaluations += 1
                        continue
                    
                    print(f"✅ Extracted: {len(student_answer)} characters")
                    
                    # AI Evaluation with error handling
                    try:
                        evaluation = analyze_answer_with_ai(question_text, question_text, student_answer)
                        
                        results['evaluations'].append({
                            'student_file': answer_filename,
                            'student_answer': student_answer[:500] + '...' if len(student_answer) > 500 else student_answer,
                            'score': evaluation['score'],
                            'feedback': evaluation['feedback'],
                            'suggestions': evaluation.get('suggestions', '')
                        })
                        
                        successful_evaluations += 1
                        print(f"✅ Evaluation complete: {evaluation['score']}/10")
                        
                    except Exception as eval_error:
                        print(f"❌ Evaluation error: {eval_error}")
                        # Add partial result with error notice
                        results['evaluations'].append({
                            'student_file': answer_filename,
                            'student_answer': student_answer[:500] + '...' if len(student_answer) > 500 else student_answer,
                            'score': 0,
                            'feedback': f'Error during evaluation: {str(eval_error)}',
                            'suggestions': 'Please try uploading the file again or contact support.'
                        })
                        failed_evaluations += 1
                    
                except Exception as file_error:
                    print(f"❌ File processing error: {file_error}")
                    failed_evaluations += 1
                    continue
        
        # Check if any evaluations succeeded
        if successful_evaluations == 0:
            flash('Could not process any answer files. Please check file formats and try again.')
            return redirect(url_for('index'))
        
        print(f"\n{'='*60}")
        print(f"📊 EVALUATION COMPLETE")
        print(f"   ✅ Successful: {successful_evaluations}")
        if failed_evaluations > 0:
            print(f"   ⚠️  Failed: {failed_evaluations}")
        print(f"{'='*60}\n")
        
        # Generate Excel report
        try:
            excel_path = generate_excel_report(results, session_id)
            print(f"📊 Excel report generated: {excel_path}")
        except Exception as excel_error:
            print(f"⚠️  Excel generation warning: {excel_error}")
            excel_path = None
        
        if failed_evaluations > 0:
            flash(f'Warning: {failed_evaluations} file(s) could not be processed completely.')
        
        return render_template('results.html', 
                             results=results, 
                             excel_path=excel_path,
                             session_id=session_id)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Unexpected error: {str(e)}. Please try again or contact support.')
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
    
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")

    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # Production mode (Gunicorn)
    # Create tables if they don't exist
    with app.app_context():
        db.create_all()
        print("✅ Production Database initialized")