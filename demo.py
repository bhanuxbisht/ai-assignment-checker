#!/usr/bin/env python3
"""
Demo Script for AI Assignment Checker
Demonstrates the functionality using sample files
"""

import os
import sys
import requests
import time
from pathlib import Path

def demo_file_upload():
    """Demonstrate file upload and evaluation"""
    print("🎯 AI Assignment Checker Demo")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ Server is running")
            print(f"   - Status: {health.get('status')}")
            print(f"   - Gemini AI: {'✅' if health.get('gemini_configured') else '❌'}")
            print(f"   - spaCy: {'✅' if health.get('spacy_loaded') else '❌'}")
        else:
            print("❌ Server returned error:", response.status_code)
            return False
    except requests.exceptions.RequestException:
        print("❌ Server is not running!")
        print("💡 Start the server first: python app.py")
        return False
    
    print("\n📁 Demo Files:")
    
    # Check demo files
    demo_files = {
        'question': 'test_data/sample_question.txt',
        'answer1': 'test_data/student_answer1.txt',
        'answer2': 'test_data/student_answer2.txt'
    }
    
    for name, path in demo_files.items():
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024
            print(f"✅ {name}: {path} ({size:.1f} KB)")
        else:
            print(f"❌ {name}: {path} (not found)")
            return False
    
    print("\n🤖 Simulating File Upload...")
    print("In a real scenario, you would:")
    print("1. Go to http://localhost:5000")
    print("2. Upload the question file")
    print("3. Upload the answer files")
    print("4. Click 'Start AI Evaluation'")
    print("5. Download the Excel report")
    
    print("\n📊 Expected Results:")
    print("- Student 1 (John): ~7-8/10 (Good understanding, informal language)")
    print("- Student 2 (Jane): ~9-10/10 (Excellent technical answer)")
    
    print("\n🎉 Demo completed! Try the real upload at http://localhost:5000")
    return True

def show_sample_content():
    """Show content of sample files"""
    print("\n📖 Sample Content Preview:")
    print("=" * 50)
    
    files = [
        ('Question Paper', 'test_data/sample_question.txt'),
        ('Student Answer 1', 'test_data/student_answer1.txt'),
        ('Student Answer 2', 'test_data/student_answer2.txt')
    ]
    
    for title, filepath in files:
        print(f"\n📄 {title}:")
        print("-" * 30)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()[:300] + "..." if len(f.read()) > 300 else content
                print(content)
        else:
            print("File not found")

def main():
    """Main demo function"""
    print("🚀 Welcome to the AI Assignment Checker Demo!\n")
    
    # Show sample content
    show_sample_content()
    
    print("\n" + "=" * 60)
    
    # Demo the upload process
    if demo_file_upload():
        print("\n✅ Demo completed successfully!")
        print("🌐 Open http://localhost:5000 to try the actual application")
    else:
        print("\n❌ Demo failed. Please check the setup.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())