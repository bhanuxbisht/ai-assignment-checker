#!/usr/bin/env python3
"""
Setup Script for AI Assignment Checker
Automates the installation and configuration process
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is adequate"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is too old")
        print("💡 Please install Python 3.9 or higher")
        return False

def create_virtual_environment():
    """Create and activate virtual environment"""
    print("🏗️  Creating virtual environment...")
    
    if os.path.exists('venv'):
        print("⚠️  Virtual environment already exists")
        return True
    
    if run_command('python -m venv venv', 'Creating virtual environment'):
        print("💡 To activate: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Linux/Mac)")
        return True
    return False

def install_dependencies():
    """Install Python dependencies"""
    print("📚 Installing Python dependencies...")
    
    # Determine pip path
    if os.name == 'nt':  # Windows
        pip_path = 'venv\\Scripts\\pip'
        python_path = 'venv\\Scripts\\python'
    else:  # Linux/Mac
        pip_path = 'venv/bin/pip'
        python_path = 'venv/bin/python'
    
    commands = [
        f'{pip_path} install --upgrade pip',
        f'{pip_path} install -r requirements.txt',
        f'{python_path} -m spacy download en_core_web_sm'
    ]
    
    for cmd in commands:
        if not run_command(cmd, f'Running: {cmd}'):
            return False
    
    return True

def setup_environment_file():
    """Set up environment variables"""
    print("🔧 Setting up environment file...")
    
    if os.path.exists('.env'):
        print("⚠️  .env file already exists")
        return True
    
    if os.path.exists('.env.example'):
        shutil.copy('.env.example', '.env')
        print("✅ Created .env file from template")
        print("💡 Please edit .env and add your Gemini API key")
        return True
    else:
        print("❌ .env.example not found")
        return False

def create_directories():
    """Create necessary directories"""
    print("📁 Creating necessary directories...")
    
    directories = ['uploads', 'results', 'static/css', 'static/js', 'templates', 'test_data']
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    return True

def check_tesseract():
    """Check if Tesseract is installed"""
    print("🔍 Checking Tesseract OCR...")
    
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Tesseract OCR is installed")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print("❌ Tesseract OCR not found")
    print("💡 Install instructions:")
    print("   Windows: https://github.com/UB-Mannheim/tesseract/wiki")
    print("   macOS: brew install tesseract")
    print("   Ubuntu: sudo apt-get install tesseract-ocr")
    return False

def run_health_check():
    """Run the health check script"""
    print("🏥 Running health check...")
    
    if os.name == 'nt':  # Windows
        python_path = 'venv\\Scripts\\python'
    else:  # Linux/Mac
        python_path = 'venv/bin/python'
    
    return run_command(f'{python_path} health_check.py', 'Health check')

def main():
    """Main setup function"""
    print("🚀 AI Assignment Checker Setup\n")
    
    steps = [
        ("Python Version", check_python_version),
        ("Directories", create_directories),
        ("Virtual Environment", create_virtual_environment),
        ("Dependencies", install_dependencies),
        ("Environment File", setup_environment_file),
        ("Tesseract OCR", check_tesseract),
        ("Health Check", run_health_check),
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        print(f"\n{'='*50}")
        print(f"Step: {step_name}")
        print('='*50)
        
        if not step_func():
            failed_steps.append(step_name)
    
    print(f"\n{'='*50}")
    print("Setup Summary")
    print('='*50)
    
    if not failed_steps:
        print("🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Edit .env file and add your Gemini API key")
        print("2. Activate virtual environment:")
        if os.name == 'nt':
            print("   venv\\Scripts\\activate")
        else:
            print("   source venv/bin/activate")
        print("3. Start the application:")
        print("   python app.py")
        print("4. Open http://localhost:5000 in your browser")
        return 0
    else:
        print(f"⚠️  Setup completed with {len(failed_steps)} issues:")
        for step in failed_steps:
            print(f"   - {step}")
        print("\nPlease resolve the issues above and run setup again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())