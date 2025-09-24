import webbrowser
import time
import requests

def open_in_browser():
    """Open AI Assignment Checker in default web browser"""
    url = "http://localhost:5000"
    
    print("🌐 Opening AI Assignment Checker in your web browser...")
    
    # Check if server is running
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            print("✅ Server is running!")
            webbrowser.open(url)
            print(f"🚀 Opened {url} in your default browser")
        else:
            print(f"❌ Server responded with status: {response.status_code}")
    except requests.exceptions.RequestException:
        print("❌ Server is not running!")
        print("💡 Start the server first with: python app.py")
        print("   Then run this script again")

if __name__ == "__main__":
    open_in_browser()