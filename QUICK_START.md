# 🚀 Quick Start Guide - AI Assignment Checker

## Get Started in 5 Minutes!

### Step 1: Setup (First Time Only)
**Windows Users:**
```cmd
double-click: setup.bat
```

**Linux/Mac Users:**
```bash
python setup.py
```

### Step 2: Configure API Key
1. Get your free Gemini AI API key: https://makersuite.google.com/app/apikey
2. Edit `.env` file and replace `your_gemini_api_key_here` with your actual key

### Step 3: Start the Server
**Windows Users:**
```cmd
double-click: start_server.bat
```

**Others:**
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Start server
python app.py
```

### Step 4: Open the Application
Open your web browser and go to: **http://localhost:5000**

### Step 5: Try the Demo
1. Upload `test_data/sample_question.txt` as the question paper
2. Upload `test_data/student_answer1.txt` and `test_data/student_answer2.txt` as answers
3. Click "Start AI Evaluation"
4. Download the Excel report

## 🎯 That's It!

Your AI Assignment Checker is now ready to help you grade assignments automatically!

## 🆘 Need Help?

- **Health Check**: Run `python health_check.py`
- **Demo**: Run `python demo.py`
- **Issues**: Check the README.md file
- **Not Working?** Make sure you have Python 3.9+ and a valid Gemini API key

## 📚 For Teachers

This tool helps you:
- ✅ Grade assignments automatically
- ✅ Get detailed feedback for each student  
- ✅ Save hours of grading time
- ✅ Provide consistent evaluation
- ✅ Export results to Excel

Happy teaching! 🎓