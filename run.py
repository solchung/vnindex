import subprocess
import sys
import os
import time
import webbrowser

def start_server():
    print("=" * 60)
    print("         VN SENSE STOCK SCREENER & SCORING SYSTEM")
    print("=" * 60)
    
    server_url = "http://127.0.0.1:8000"
    
    # Check if static folder exists
    if not os.path.exists("static"):
        print("Error: 'static' folder not found. Please run the script in the project root directory.")
        sys.exit(1)
        
    print(f"\n1. Opening default web browser to: {server_url}")
    # Open browser slightly after starting to ensure server has a head start
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(server_url)
        
    import threading
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    print("2. Starting FastAPI web server via uvicorn...")
    print("   Press Ctrl+C to terminate the application.\n")
    
    try:
        import uvicorn
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\nServer stopped by user. Goodbye!")
    except Exception as e:
        print(f"\nFailed to start server: {e}")
        print("Attempting to launch using python -m uvicorn...")
        try:
            subprocess.run([sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000"])
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    # Ensure current directory is the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    start_server()
