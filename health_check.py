#!/usr/bin/env python3
"""
Health Check Script for AI Assignment Checker
This script tests all major components of the application
"""

import sys
import os
import requests
import subprocess
import tempfile
from pathlib import Path

def test_python_environment():
    """Test Python environment and dependencies"""
    print("🐍 Testing Python environment...")
    
    try:
        import flask
        print(f"✅ Flask version: {flask.__version__}")
    except ImportError:
        print("❌ Flask not installed")
        return False
    
    try:
        import google.generativeai as genai
        print("✅ Google Generative AI imported successfully")
    except ImportError:
        print("❌ Google Generative AI not installed")
        return False
    
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print("✅ spaCy model loaded successfully")
    except (ImportError, OSError) as e:
        print(f"❌ spaCy issue: {e}")
        return False
    
    try:
        import pytesseract
        from PIL import Image
        print("✅ Tesseract OCR and Pillow available")
    except ImportError:
        print("❌ Tesseract OCR or Pillow not available")
        return False
    
    return True

def test_tesseract():
    """Test Tesseract OCR installation"""
    print("\n🔍 Testing Tesseract OCR...")
    
    # First try the PATH
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line} (found in PATH)")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # Try common Windows paths
    if os.name == 'nt':  # Windows
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        
        for path in tesseract_paths:
            if os.path.exists(path):
                try:
                    result = subprocess.run([path, '--version'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        version_line = result.stdout.split('\n')[0]
                        print(f"✅ {version_line} (found at {path})")
                        return True
                except Exception:
                    continue
    
    print("❌ Tesseract not found")
    print("💡 Install Tesseract OCR:")
    print("   - Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    print("   - macOS: brew install tesseract")
    print("   - Ubuntu: sudo apt-get install tesseract-ocr")
    return False

def test_flask_app():
    """Test Flask application"""
    print("\n🌐 Testing Flask application...")
    
    try:
        # Import and create app
        from app import app
        
        with app.test_client() as client:
            # Test main route
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Main route working")
            else:
                print(f"❌ Main route failed: {response.status_code}")
                return False
            
            # Test health endpoint
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Health endpoint working")
                health_data = response.get_json()
                print(f"   - Status: {health_data.get('status')}")
                print(f"   - Gemini configured: {health_data.get('gemini_configured')}")
                print(f"   - spaCy loaded: {health_data.get('spacy_loaded')}")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Flask app error: {e}")
        return False

def test_file_processing():
    """Test file processing capabilities"""
    print("\n📄 Testing file processing...")
    
    try:
        from app import extract_text_from_file
        
        # Create a test text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test document for AI assignment checking.")
            test_file = f.name
        
        # Test text extraction
        text = extract_text_from_file(test_file)
        if "test document" in text:
            print("✅ Text file processing working")
            os.unlink(test_file)  # Clean up
            return True
        else:
            print("❌ Text extraction failed")
            os.unlink(test_file)  # Clean up
            return False
            
    except Exception as e:
        print(f"❌ File processing error: {e}")
        return False

def test_directories():
    """Test required directories"""
    print("\n📁 Testing directories...")
    
    required_dirs = ['uploads', 'results', 'static', 'templates']
    all_good = True
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"❌ {dir_name}/ directory missing")
            all_good = False
    
    return all_good

def test_environment_variables():
    """Test environment variables"""
    print("\n🔧 Testing environment variables...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    gemini_key = os.getenv('GEMINI_API_KEY')
    secret_key = os.getenv('SECRET_KEY')
    
    if gemini_key and gemini_key != 'your_gemini_api_key_here':
        print("✅ GEMINI_API_KEY is set")
    else:
        print("⚠️  GEMINI_API_KEY not configured (using fallback mode)")
        print("💡 Get your API key from: https://makersuite.google.com/app/apikey")
    
    if secret_key and secret_key != 'your_secret_key_here':
        print("✅ SECRET_KEY is set")
    else:
        print("⚠️  SECRET_KEY using default value (change for production)")
    
    return True

def main():
    """Run all health checks"""
    print("🚀 AI Assignment Checker - Health Check\n")
    
    tests = [
        ("Python Environment", test_python_environment),
        ("Tesseract OCR", test_tesseract),
        ("Directories", test_directories),
        ("Environment Variables", test_environment_variables),
        ("File Processing", test_file_processing),
        ("Flask Application", test_flask_app),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All checks passed! Your AI Assignment Checker is ready to use.")
        print("🌐 Start the server with: python app.py")
        return 0
    else:
        print("⚠️  Some checks failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())