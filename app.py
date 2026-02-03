import os
import uuid
import gc
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, render_template, jsonify, send_file, flash, redirect, url_for

# Try to import caching module with graceful fallback
try:
    from cache import (
        cache_ocr_result, 
        cache_ai_evaluation, 
        get_cache_stats, 
        clear_cache,
        CACHE_ENABLED
    )
    CACHING_AVAILABLE = True
    print("✅ Caching module loaded")
except ImportError as e:
    print(f"⚠️  Cache module not available: {e}")
    print("   Running without Redis caching (system works fine)")
    CACHING_AVAILABLE = False
    CACHE_ENABLED = False
    # No-op decorators when cache module unavailable
    def cache_ocr_result(func):
        return func
    def cache_ai_evaluation(func):
        return func
    def get_cache_stats():
        return {'enabled': False, 'connected': False}
    def clear_cache(pattern=None):
        return 0
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import pytesseract
from pypdf import PdfReader
import pandas as pd
import spacy
from datetime import datetime
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
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max for large batch uploads

# BATCH PROCESSING CONFIGURATION
BATCH_SIZE = 10  # Process files in batches of 10 for memory efficiency
MAX_WORKERS = min(8, os.cpu_count() or 4)  # Thread pool size
PDF_CACHE = {}  # Cache for extracted PDF text
CACHE_LOCK = threading.Lock()

# Progress tracking for real-time updates
PROGRESS_STORE = {}  # {session_id: {current, total, percentage, status, start_time}}
PROGRESS_LOCK = threading.Lock()

def update_progress(session_id, current, total, status="processing"):
    """Update progress for a session"""
    with PROGRESS_LOCK:
        percentage = int((current / total) * 100) if total > 0 else 0
        PROGRESS_STORE[session_id] = {
            'current': current,
            'total': total,
            'percentage': percentage,
            'status': status,
            'timestamp': time.time()
        }

def get_progress(session_id):
    """Get progress for a session"""
    with PROGRESS_LOCK:
        return PROGRESS_STORE.get(session_id, {
            'current': 0,
            'total': 0,
            'percentage': 0,
            'status': 'unknown'
        })

def clear_progress(session_id):
    """Clear progress for a session"""
    with PROGRESS_LOCK:
        if session_id in PROGRESS_STORE:
            del PROGRESS_STORE[session_id]

# Ensure upload and results folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Configure Gemini AI (BACKUP for evaluation)
gemini_api_key = os.getenv('GEMINI_API_KEY')
if gemini_api_key and gemini_api_key != 'your_gemini_api_key_here':
    try:
        genai.configure(api_key=gemini_api_key)
        # Use the stable working model (Gemini 2.0 Flash)
        model = genai.GenerativeModel('gemini-2.0-flash')
        print("✅ Gemini AI configured as BACKUP evaluator (gemini-2.0-flash)")
    except Exception as e:
        print(f"❌ Gemini AI configuration failed: {e}")
        print("💡 Please check your API key in .env file")
        model = None
else:
    print("⚠️  Gemini API key not set - using fallback NLP scoring")
    print("💡 Add your API key to .env file for AI-powered evaluation")
    model = None

# Configure Groq AI (Fast LLM Inference) - PRIMARY for both OCR & Evaluation
groq_api_key = os.getenv('GROQ_API_KEY')
groq_api_url = "https://api.groq.com/openai/v1/chat/completions"
if groq_api_key:
    print("✅ Groq AI configured as PRIMARY (OCR + Evaluation) - console.groq.com")
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

def get_file_hash(file_path):
    """Generate hash of file for caching purposes"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        # Read in chunks for memory efficiency
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def calculate_ocr_confidence(text):
    """
    Estimate OCR quality by analyzing extracted text.
    Returns confidence score 0-100.
    
    Factors:
    - Word count (more words = more content)
    - Alphanumeric ratio (good text = 70-95% alphanumeric)
    - Average word length (normal = 3-10 chars)
    """
    if not text or not text.strip():
        return 0
    
    # Clean text
    clean_text = text.strip()
    words = clean_text.split()
    word_count = len(words)
    
    # Very short text is suspicious
    if word_count < 5:
        return 20
    
    # Calculate alphanumeric ratio
    total_chars = len(clean_text.replace(' ', '').replace('\n', ''))
    if total_chars == 0:
        return 0
    
    alnum_chars = sum(1 for c in clean_text if c.isalnum())
    alnum_ratio = alnum_chars / total_chars
    
    # Good text typically has 70-95% alphanumeric characters
    # Too high (>98%) might be garbled, too low (<50%) has too much noise
    if 0.70 <= alnum_ratio <= 0.95:
        ratio_score = 100
    elif 0.50 <= alnum_ratio < 0.70:
        ratio_score = 60
    elif 0.95 < alnum_ratio <= 0.99:
        ratio_score = 80
    else:
        ratio_score = 30
    
    # Average word length check (normal English = 4-5 chars)
    avg_word_len = sum(len(w) for w in words) / word_count if word_count > 0 else 0
    if 3 <= avg_word_len <= 10:
        length_score = 100
    elif 2 <= avg_word_len < 3 or 10 < avg_word_len <= 15:
        length_score = 60
    else:
        length_score = 30
    
    # Word count contribution (more content = more reliable)
    if word_count >= 50:
        count_score = 100
    elif word_count >= 20:
        count_score = 80
    elif word_count >= 10:
        count_score = 60
    else:
        count_score = 40
    
    # Weighted average
    confidence = (ratio_score * 0.4 + length_score * 0.3 + count_score * 0.3)
    
    return int(confidence)

def groq_vision_ocr(image, page_num=1):
    """
    Use Groq's Llama 3.2 Vision for OCR - fast and accurate.
    Standalone function for use in both PDF and image OCR.
    """
    import io
    import base64
    import requests
    
    if not groq_api_key:
        return None
        
    try:
        # Convert PIL Image to base64
        buffered = io.BytesIO()
        # Resize to reduce payload size
        max_width = 1200
        if image.width > max_width:
            ratio = max_width / image.width
            new_size = (max_width, int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)
        image.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_api_key}"
        }
        
        payload = {
            "model": "llama-3.2-90b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract ALL text from this handwritten document image. Read carefully and output ONLY the extracted text, preserving structure (headings, paragraphs, lists). Include any mathematical formulas. Correct obvious spelling errors. Mark any unclear text with [?]."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4096
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        result = response.json()
        text = result['choices'][0]['message']['content'].strip()
        return text if len(text) > 20 else None
        
    except Exception as e:
        print(f"   ⚠️ Groq Vision error on page {page_num}: {str(e)[:50]}")
        return None

@cache_ocr_result
def extract_text_from_pdf(pdf_path):
    """ULTRA-FAST PDF extraction with CACHING (supports both digital and image-based PDFs)"""
    # Check cache first for repeated file access
    file_hash = get_file_hash(pdf_path)
    with CACHE_LOCK:
        if file_hash in PDF_CACHE:
            print(f"⚡ CACHE HIT: Using cached text for {os.path.basename(pdf_path)}")
            return PDF_CACHE[file_hash]
    
    try:
        # SPEED OPTIMIZATION: Try digital text extraction first (instant)
        with open(pdf_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # If text was extracted successfully, cache and return it immediately
        if text.strip() and len(text) > 100:  # At least 100 chars for valid text
            print(f"⚡ FAST: Extracted digital text ({len(text)} chars) - NO OCR NEEDED")
            with CACHE_LOCK:
                PDF_CACHE[file_hash] = text
            return text
        
        # If no text found, try OCR on PDF images (for scanned/photo-based PDFs)
        print("📸 Photo-based/Handwritten PDF detected. Using AI VISION OCR...")
        try:
            from pdf2image import convert_from_path
            import os
            import time
            import io
            import base64
            import requests
            
            ocr_start = time.time()
            
            # Set poppler path for Windows
            poppler_path = None
            possible_paths = [
                os.path.expanduser("~/poppler/poppler-24.08.0/Library/bin"),
                "C:\\Users\\Bhanu Bisht\\poppler\\poppler-24.08.0\\Library\\bin",
                "C:\\Program Files\\poppler\\poppler-24.08.0\\Library\\bin",
                os.path.expanduser("~/poppler/Library/bin")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    poppler_path = path
                    break
            
            # Use 150 DPI - faster conversion, still good quality
            print("   🔍 Converting PDF pages to images (150 DPI)...")
            if poppler_path:
                images = convert_from_path(pdf_path, dpi=150, poppler_path=poppler_path, thread_count=4)
            else:
                images = convert_from_path(pdf_path, dpi=150, thread_count=4)
            
            total_pages = len(images)
            print(f"📄 Converted {total_pages} page(s) ({time.time()-ocr_start:.1f}s)")
            
            # PRIMARY: Use Groq Vision (Llama 3.2) - generous free limits!
            print("   🧠 Using GROQ VISION AI (Llama 3.2) for handwriting extraction...")
            all_text = []
            
            for i, image in enumerate(images):
                page_text = None
                
                # Try Groq Vision first (PRIMARY - generous quota)
                page_text = groq_vision_ocr(image, i+1)
                
                if page_text:
                    print(f"   ✓ Page {i+1}/{total_pages}: {len(page_text)} chars (Groq Vision)")
                    all_text.append(page_text)
                    continue
                
                # Fallback: Tesseract with preprocessing
                try:
                    from PIL import ImageEnhance, ImageFilter
                    gray = image.convert('L')
                    contrast = ImageEnhance.Contrast(gray).enhance(1.5)
                    sharp = contrast.filter(ImageFilter.SHARPEN)
                    fallback = pytesseract.image_to_string(sharp, lang='eng', config='--oem 3 --psm 3')
                    if fallback.strip():
                        all_text.append(fallback.strip())
                        print(f"   ✓ Page {i+1}/{total_pages}: {len(fallback.strip())} chars (Tesseract)")
                except Exception as e:
                    print(f"   ⚠️ Page {i+1} all methods failed: {e}")
            
            ocr_text = "\n\n--- Page Break ---\n\n".join(all_text)
            elapsed = time.time() - ocr_start
            
            if ocr_text.strip():
                print(f"✅ AI VISION OCR: {len(ocr_text)} chars from {total_pages} pages in {elapsed:.1f}s")
                with CACHE_LOCK:
                    PDF_CACHE[file_hash] = ocr_text
                return ocr_text
            else:
                print(f"⚠️  No text extracted ({elapsed:.1f}s)")
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

@cache_ocr_result
def extract_text_from_image(image_path):
    """
    Extract text from image file with confidence-based method selection.
    - First tries fast Tesseract OCR
    - If confidence < 60%, automatically falls back to Groq Vision AI
    """
    try:
        image = Image.open(image_path)
        
        # Step 1: Try fast Tesseract first
        config = r'--oem 3 --psm 3'
        tesseract_text = pytesseract.image_to_string(image, config=config, lang='eng')
        
        # Step 2: Calculate confidence
        confidence = calculate_ocr_confidence(tesseract_text)
        chars = len(tesseract_text.strip())
        
        # Step 3: Decide based on confidence
        if confidence >= 60:
            # Good quality - use Tesseract result (fast + free)
            print(f"📊 OCR: {chars} chars, confidence: {confidence}%, method: Tesseract")
            return tesseract_text.strip()
        else:
            # Low confidence - likely handwriting, use Groq Vision
            print(f"📊 OCR: {chars} chars, confidence: {confidence}% (low), method: Groq Vision AI")
            vision_text = extract_text_from_image_pil(image)
            if vision_text and len(vision_text.strip()) > len(tesseract_text.strip()):
                return vision_text
            else:
                # Vision didn't help, return what we have
                return tesseract_text.strip() if tesseract_text.strip() else vision_text
    
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

def extract_text_from_image_pil(image):
    """Groq Vision AI for images - PRIMARY for handwriting"""
    try:
        # PRIMARY: Use Groq Vision (Llama 3.2 90B) - generous limits!
        if groq_api_key:
            try:
                # Resize if too large
                max_width = 1500
                if image.width > max_width:
                    ratio = max_width / image.width
                    new_size = (max_width, int(image.height * ratio))
                    image = image.resize(new_size, Image.LANCZOS)
                
                text = groq_vision_ocr(image)
                if text:
                    print(f"✅ Groq Vision extracted: {len(text)} chars (PRIMARY)")
                    return text
            except Exception as e:
                print(f"⚠️ Groq Vision failed: {e}")
        
        # Fallback to Tesseract
        config = r'--oem 3 --psm 3'
        text = pytesseract.image_to_string(image, config=config, lang='eng')
        return text.strip()
    except Exception as e:
        print(f"❌ OCR error: {e}")
        return ""

def extract_text_from_file(file_path):
    """Extract text from various file types with memory optimization"""
    file_extension = file_path.rsplit('.', 1)[1].lower()
    
    if file_extension == 'pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension in ['png', 'jpg', 'jpeg', 'gif']:
        return extract_text_from_image(file_path)
    elif file_extension == 'txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    else:
        return ""

def process_single_file(file_data):
    """Process a single answer file - designed for parallel execution"""
    i, answer_path, answer_filename, question_text = file_data
    try:
        student_answer = extract_text_from_file(answer_path)
        
        if not student_answer.strip():
            return {
                'success': False,
                'index': i,
                'filename': answer_filename,
                'error': 'No text extracted'
            }
        
        # AI Evaluation
        evaluation = analyze_answer_with_ai(question_text, question_text, student_answer)
        
        # Force garbage collection for large files
        gc.collect()
        
        return {
            'success': True,
            'index': i,
            'filename': answer_filename,
            'student_answer': student_answer[:500] + '...' if len(student_answer) > 500 else student_answer,
            'score': evaluation['score'],
            'feedback': evaluation['feedback'],
            'suggestions': evaluation.get('suggestions', '')
        }
    except Exception as e:
        return {
            'success': False,
            'index': i,
            'filename': answer_filename,
            'error': str(e)
        }

def batch_process_files(file_list, question_text, batch_size=BATCH_SIZE, session_id=None):
    """
    Process files in optimized batches for memory efficiency and speed.
    Handles 100+ files efficiently with parallel processing.
    Now includes real-time progress tracking.
    """
    results = []
    total_files = len(file_list)
    total_batches = (total_files + batch_size - 1) // batch_size
    processed_count = 0
    
    print(f"\n🚀 BATCH PROCESSING: {total_files} files in {total_batches} batches")
    print(f"   Using {MAX_WORKERS} parallel workers")
    
    # Initialize progress
    if session_id:
        update_progress(session_id, 0, total_files, "starting")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_files)
        batch = file_list[start_idx:end_idx]
        
        print(f"\n📦 Processing Batch {batch_num + 1}/{total_batches} ({len(batch)} files)...")
        
        # Process batch in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks in batch
            future_to_file = {
                executor.submit(process_single_file, (i, path, filename, question_text)): (i, filename)
                for i, path, filename in batch
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)
                processed_count += 1
                
                # Update progress
                if session_id:
                    update_progress(session_id, processed_count, total_files, "processing")
                
                if result['success']:
                    print(f"   ✅ {result['filename']}: Score {result['score']}/10")
                else:
                    print(f"   ⚠️  {result['filename']}: {result.get('error', 'Failed')}")
        
        # Memory cleanup between batches
        gc.collect()
        print(f"   Batch {batch_num + 1} complete. Memory cleaned.")
    
    # Mark as complete
    if session_id:
        update_progress(session_id, total_files, total_files, "complete")
    
    # Sort results by original index
    results.sort(key=lambda x: x['index'])
    return results

@cache_ai_evaluation
def analyze_answer_with_ai(question, correct_answer, student_answer):
    """FAIR & UNBIASED AI Evaluation - GROQ PRIMARY, Gemini Backup"""
    
    def clean_markdown(text):
        """Remove markdown formatting like ** and * from text"""
        if not text:
            return text
        # Remove bold markers **text** and *text*
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        # Remove any remaining stray asterisks
        text = text.replace('**', '').replace('*', '')
        return text.strip()
    
    # Try Groq FIRST (PRIMARY - generous quota!)
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
                        "content": """You are an experienced, FAIR teacher evaluating handwritten student answers that were OCR-scanned.

CRITICAL RULES:
1. The text contains OCR errors from handwriting - DO NOT penalize OCR mistakes
2. Focus on CONCEPTS and KNOWLEDGE demonstrated, not text quality
3. If you can understand what the student meant, GIVE FULL CREDIT
4. Be encouraging and constructive in feedback
5. DO NOT use markdown formatting (no asterisks, no bold, no bullets)
6. Write in plain text only"""
                    },
                    {
                        "role": "user",
                        "content": f"""Evaluate this student's handwritten answer (OCR-extracted):

QUESTION: {question}

REFERENCE ANSWER: {correct_answer}

STUDENT'S ANSWER (from handwriting): {student_answer}

Provide your evaluation in this EXACT format (plain text, no asterisks or markdown):

SCORE: [number 0-10]
Where: 9-10 = Excellent (comprehensive understanding)
       7-8 = Good (solid grasp of key concepts)
       5-6 = Satisfactory (partial understanding)
       3-4 = Needs improvement (limited understanding)
       0-2 = Insufficient (major gaps)

ANALYSIS:
Write 2-3 sentences analyzing what the student understands well. Mention specific concepts they got right. Be positive and encouraging.

SUGGESTIONS FOR IMPROVEMENT:
1. [First actionable tip to improve their answer]
2. [Second tip focusing on concepts to study more]
3. [Third tip for exam technique or clarity]

Remember: Plain text only, no formatting symbols."""
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 512
            }
            
            response = requests.post(groq_api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            text = result['choices'][0]['message']['content'].strip()
            
            # Parse Groq response
            score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            feedback_match = re.search(r'ANALYSIS:\s*(.+?)(?=SUGGESTIONS|$)', text, re.IGNORECASE | re.DOTALL)
            suggestions_match = re.search(r'SUGGESTIONS[^:]*:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            
            score = float(score_match.group(1)) if score_match else 5
            feedback = clean_markdown(feedback_match.group(1).strip()) if feedback_match else clean_markdown(text)
            suggestions = clean_markdown(suggestions_match.group(1).strip()) if suggestions_match else "Review the concepts mentioned in class"
            
            # Validate score
            score = max(0, min(10, score))
            
            print(f"✅ Groq AI evaluated successfully - Score: {score}/10 (PRIMARY)")
            return {
                'score': round(score, 1),
                'feedback': feedback,
                'suggestions': suggestions
            }
        except Exception as groq_error:
            print(f"⚠️  Groq failed: {groq_error}")
            # Continue to Gemini backup
    
    # Try Gemini as BACKUP
    if model:
        try:
            prompt = f"""You are a FAIR teacher evaluating a student's handwritten answer (OCR-extracted).

RULES:
- OCR may have errors - focus on MEANING not text quality
- Be encouraging and constructive
- DO NOT use markdown (no asterisks, bold, or special formatting)
- Write in plain text only

QUESTION: {question}
REFERENCE: {correct_answer}
STUDENT ANSWER: {student_answer}

Respond in this EXACT format (plain text only):

SCORE: [0-10]

ANALYSIS:
[2-3 sentences about what the student understands. Be positive.]

SUGGESTIONS FOR IMPROVEMENT:
1. [First tip]
2. [Second tip]
3. [Third tip]"""
            
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 512,
                }
            )
            text = response.text.strip()
            
            # Parse the response
            score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
            feedback_match = re.search(r'ANALYSIS:\s*(.+?)(?=SUGGESTIONS|$)', text, re.IGNORECASE | re.DOTALL)
            suggestions_match = re.search(r'SUGGESTIONS[^:]*:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
            
            score = float(score_match.group(1)) if score_match else 5
            feedback = clean_markdown(feedback_match.group(1).strip()) if feedback_match else clean_markdown(text)
            suggestions = clean_markdown(suggestions_match.group(1).strip()) if suggestions_match else "Review the concepts mentioned in class"
            
            if score < 0 or score > 10:
                score = max(0, min(10, score))
            
            print(f"✅ Gemini AI evaluated successfully - Score: {score}/10 (BACKUP)")
            return {
                'score': round(score, 1),
                'feedback': feedback,
                'suggestions': suggestions
            }
        except Exception as gemini_error:
            print(f"⚠️  Gemini failed: {gemini_error}")
    
    # Fallback to spaCy-based evaluation
    print("⚠️  Using spaCy fallback evaluation")
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
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
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
        
        # OPTIMIZED: Batch processing for large datasets (100+ files)
        valid_files = [f for f in answer_files if f and f.filename and allowed_file(f.filename)]
        total_files = len(valid_files)
        print(f"\n📚 Processing {total_files} student answer(s)...")
        
        # Check if we should use batch processing (for 5+ files)
        if total_files >= 5:
            print(f"🚀 Using OPTIMIZED BATCH PROCESSING (efficient for large datasets)")
            
            # Initialize progress tracking for this session
            update_progress(session_id, 0, total_files, "saving files")
            
            # Step 1: Save all files first (fast I/O)
            file_list = []
            for i, answer_file in enumerate(valid_files):
                answer_filename = secure_filename(answer_file.filename)
                answer_path = os.path.join(session_folder, f'answer_{i}_{answer_filename}')
                try:
                    answer_file.save(answer_path)
                    file_list.append((i, answer_path, answer_filename))
                except Exception as save_err:
                    print(f"⚠️  Failed to save {answer_filename}: {save_err}")
            
            # Step 2: Batch process all files in parallel (with progress tracking)
            batch_results = batch_process_files(file_list, question_text, session_id=session_id)
            
            # Step 3: Compile results
            successful_evaluations = 0
            failed_evaluations = 0
            
            for result in batch_results:
                if result['success']:
                    results['evaluations'].append({
                        'student_file': result['filename'],
                        'student_answer': result['student_answer'],
                        'score': result['score'],
                        'feedback': result['feedback'],
                        'suggestions': result['suggestions']
                    })
                    successful_evaluations += 1
                else:
                    results['evaluations'].append({
                        'student_file': result['filename'],
                        'student_answer': '',
                        'score': 0,
                        'feedback': f'Error: {result.get("error", "Processing failed")}',
                        'suggestions': 'Please try uploading the file again.'
                    })
                    failed_evaluations += 1
        else:
            # Sequential processing for small batches (< 5 files)
            successful_evaluations = 0
            failed_evaluations = 0
            
            for i, answer_file in enumerate(valid_files):
                answer_filename = secure_filename(answer_file.filename)
                answer_path = os.path.join(session_folder, f'answer_{i}_{answer_filename}')
                
                try:
                    print(f"\n--- Student {i+1}: {answer_filename} ---")
                    answer_file.save(answer_path)
                    
                    student_answer = extract_text_from_file(answer_path)
                    
                    if not student_answer.strip():
                        print(f"⚠️  No text extracted from {answer_filename} - Skipping")
                        failed_evaluations += 1
                        continue
                    
                    print(f"✅ Extracted: {len(student_answer)} characters")
                    
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
                    
                except Exception as file_error:
                    print(f"❌ File processing error: {file_error}")
                    failed_evaluations += 1
                    continue
        
        # Clear cache after processing to free memory
        with CACHE_LOCK:
            PDF_CACHE.clear()
        gc.collect()
        
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
    """Health check endpoint with optimization status and cache stats"""
    cache_stats = get_cache_stats()
    return jsonify({
        'status': 'healthy',
        'gemini_configured': model is not None,
        'groq_configured': groq_api_key is not None,
        'spacy_loaded': nlp is not None,
        'optimizations': {
            'batch_processing': True,
            'batch_size': BATCH_SIZE,
            'max_workers': MAX_WORKERS,
            'pdf_cache_enabled': True,
            'redis_cache_enabled': cache_stats.get('enabled', False),
            'redis_connected': cache_stats.get('connected', False),
            'parallel_ocr': True,
            'max_upload_mb': 100
        },
        'cache': {
            'hit_rate': cache_stats.get('hit_rate', 0),
            'total_keys': cache_stats.get('total_keys', 0)
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/cache/stats')
def cache_stats_endpoint():
    """Get detailed cache statistics"""
    stats = get_cache_stats()
    return jsonify({
        'cache_statistics': stats,
        'memory_cache': {
            'pdf_cache_size': len(PDF_CACHE)
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """Clear all cached data (requires secret key confirmation)"""
    confirm_key = request.json.get('key', '') if request.is_json else request.form.get('key', '')
    
    if confirm_key != app.secret_key[:8]:  # Use first 8 chars of secret key as confirmation
        return jsonify({'error': 'Invalid confirmation key'}), 403
    
    # Clear Redis cache
    redis_cleared = clear_cache()
    
    # Clear in-memory PDF cache
    with CACHE_LOCK:
        pdf_cleared = len(PDF_CACHE)
        PDF_CACHE.clear()
    
    return jsonify({
        'success': True,
        'redis_keys_cleared': redis_cleared,
        'pdf_cache_cleared': pdf_cleared,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/upload/progress/<session_id>')
def get_upload_progress(session_id):
    """Get real-time progress for an upload session"""
    progress = get_progress(session_id)
    return jsonify(progress)

@app.route('/api/stats')
def get_stats():
    """Get processing statistics"""
    cache_stats = get_cache_stats()
    return jsonify({
        'cache_size': len(PDF_CACHE),
        'batch_size': BATCH_SIZE,
        'max_workers': MAX_WORKERS,
        'cpu_count': os.cpu_count(),
        'redis_cache': cache_stats,
        'caching_available': CACHING_AVAILABLE
    })

if __name__ == '__main__':
    print("Starting AI Assignment Checker...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Results folder: {RESULTS_FOLDER}")
    print(f"Gemini AI configured: {model is not None}")
    print(f"spaCy loaded: {nlp is not None}")
    print(f"🚀 Batch Processing: ENABLED (batch_size={BATCH_SIZE}, workers={MAX_WORKERS})")
    print("✅ Open access mode - No authentication required")

    app.run(debug=True, host='0.0.0.0', port=5000)