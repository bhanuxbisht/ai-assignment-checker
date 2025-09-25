# AI Assignment Checker 🤖📚

An intelligent web application that helps teachers automatically evaluate student assignments using AI, OCR, and NLP technologies. Upload question papers and student answers, and get detailed evaluations with scores and feedback in seconds!

**🎯 Last Updated: September 24, 2025 - Fully functional and deployed!**

![AI Assignment Checker](https://img.shields.io/badge/AI%20Powered-Gemini%20AI-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-green)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-red)

## ✨ Features

- **🔍 OCR Technology**: Extract text from PDFs and images automatically
- **🧠 AI-Powered Evaluation**: Uses Google's Gemini AI for intelligent answer assessment
- **📊 Comprehensive Reports**: Generate detailed Excel reports with scores and feedback
- **🎨 Modern UI**: Clean, responsive web interface built with Bootstrap
- **📁 Multi-Format Support**: Supports PDF, PNG, JPG, JPEG, GIF, and TXT files
- **⚡ Fast Processing**: Batch process multiple student answers simultaneously
- **💬 Detailed Feedback**: Get specific suggestions for student improvement

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher (3.11+ recommended)
- pip (Python package manager)
- Tesseract OCR (for image text extraction)
- Google Gemini API key

## 🚀 Quick Start (Choose Your Method)

### 🐳 Option 1: Docker (Easiest - Recommended for Testing)

**For friends who just want to try the app:**

```bash
# 1. Install Docker Desktop (one-time setup)
# 2. Run the app instantly
docker run -p 5000:5000 -e GEMINI_API_KEY=your_api_key bhanuxbisht/ai-assignment-checker

# 3. Open browser: http://localhost:5000
```

**Benefits:** ✅ No Python installation ✅ No dependencies ✅ Works on all OS

### 💻 Option 2: Traditional Installation (For Developers)

**For friends who want to modify the code:**

#### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ai-assignment-checker
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install spaCy language model**
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Install Tesseract OCR**
   
   **Windows:**
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Add to PATH or set TESSERACT_CMD environment variable
   
   **macOS:**
   ```bash
   brew install tesseract
   ```
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install tesseract-ocr
   ```

6. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file and add your keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   SECRET_KEY=your_secret_key_here
   ```

7. **Run the application**
   ```bash
   python app.py
   ```

8. **Open your browser**
   Navigate to: http://localhost:5000

## 🔧 Configuration

### Getting Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key to your `.env` file

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini AI API key | Yes |
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `FLASK_ENV` | Environment (development/production) | No |
| `FLASK_DEBUG` | Enable debug mode | No |

## 📖 Usage Guide

### For Teachers

1. **Upload Question Paper**
   - Click "Choose File" under "Question Paper"
   - Select your question paper (PDF or image)

2. **Upload Student Answers**
   - Click "Choose Files" under "Student Answer Sheets"
   - Select multiple student answer files
   - You can select multiple files at once

3. **Start Evaluation**
   - Click "Start AI Evaluation"
   - Wait for processing (may take 1-3 minutes depending on file size)

4. **Review Results**
   - View individual student scores and feedback
   - See summary statistics (average, highest, lowest scores)
   - Read detailed AI feedback for each answer

5. **Download Report**
   - Click "Download Excel Report"
   - Get a comprehensive spreadsheet with all results

### Supported File Formats

- **PDF**: Text-based and scanned PDFs
- **Images**: PNG, JPG, JPEG, GIF
- **Text**: Plain text files (.txt)
- **File Size**: Maximum 16MB per file

## 🏗️ Project Structure

```
ai-assignment-checker/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── README.md             # This file
├── uploads/              # Uploaded files storage
├── results/              # Generated reports storage
├── static/               # Static assets
│   ├── css/
│   │   └── style.css     # Custom styles
│   └── js/
│       └── main.js       # JavaScript functionality
└── templates/            # HTML templates
    ├── base.html         # Base template
    ├── index.html        # Upload form
    └── results.html      # Results display
```

## 🐳 Docker Deployment (Optional)

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.11-slim
   
   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       tesseract-ocr \
       && rm -rf /var/lib/apt/lists/*
   
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   # Download spaCy model
   RUN python -m spacy download en_core_web_sm
   
   COPY . .
   
   EXPOSE 5000
   CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
   ```

2. **Build and run**
   ```bash
   docker build -t ai-assignment-checker .
   docker run -p 5000:5000 --env-file .env ai-assignment-checker
   ```

## 🌐 Production Deployment

### Using Gunicorn

1. **Install Gunicorn** (already in requirements.txt)
   
2. **Run with Gunicorn**
   ```bash
   gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
   ```

### Deploy to Heroku

1. **Create Procfile**
   ```
   web: gunicorn app:app
   ```

2. **Create runtime.txt**
   ```
   python-3.11.0
   ```

3. **Deploy**
   ```bash
   heroku create your-app-name
   heroku config:set GEMINI_API_KEY=your_key
   heroku config:set SECRET_KEY=your_secret_key
   git push heroku main
   ```

### Deploy to Railway/Render

1. Connect your GitHub repository
2. Set environment variables in the dashboard
3. Deploy with auto-scaling

## 🔍 Troubleshooting

### Common Issues

1. **"spaCy model not found"**
   ```bash
   python -m spacy download en_core_web_sm
   ```

2. **"Tesseract not found"**
   - Ensure Tesseract is installed and in PATH
   - On Windows, set TESSERACT_CMD environment variable

3. **"Gemini AI not configured"**
   - Check your API key in `.env` file
   - Ensure the key is valid and has proper permissions

4. **File upload errors**
   - Check file size (max 16MB)
   - Ensure file format is supported
   - Verify upload folder permissions

5. **Poor OCR results**
   - Use high-quality, clear images
   - Ensure good contrast between text and background
   - Consider preprocessing images for better results

### Debug Mode

Enable debug mode for detailed error messages:

```python
# In app.py
app.run(debug=True)
```

Or set environment variable:
```bash
export FLASK_DEBUG=1
```

## 🧪 Testing

### Test the Application

1. **Health Check**
   ```
   GET /health
   ```

2. **Upload Test Files**
   - Use sample PDF and image files
   - Test with different file formats
   - Try batch uploads

3. **Verify AI Responses**
   - Check if Gemini AI is responding
   - Validate score calculations
   - Test feedback generation

### Sample Test Files

Create test files in `test_data/`:
- `sample_question.pdf` - A simple question paper
- `sample_answer1.pdf` - Student answer 1
- `sample_answer2.jpg` - Student answer 2 (image)

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main upload form |
| `/upload` | POST | Process uploaded files |
| `/download/<filename>` | GET | Download Excel report |
| `/health` | GET | Health check status |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter any issues:

1. Check the troubleshooting section above
2. Review the console output for error messages
3. Ensure all dependencies are properly installed
4. Verify environment variables are set correctly

## 🙏 Acknowledgments

- **Google Gemini AI** for intelligent evaluation
- **Tesseract OCR** for text extraction
- **spaCy** for natural language processing
- **Flask** for the web framework
- **Bootstrap** for the responsive UI

## 📈 Future Enhancements

- [ ] Support for more file formats (DOCX, PPTX)
- [ ] Real-time progress tracking
- [ ] User authentication and assignment history
- [ ] Custom rubric creation
- [ ] Integration with Learning Management Systems
- [ ] Multi-language support
- [ ] Advanced analytics and insights
- [ ] Plagiarism detection
- [ ] Voice note evaluation

---

**Made with ❤️ for educators worldwide**