import subprocess
import os
import time
import sys
import webbrowser
import signal

# Get project root directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "offerClick", "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "offerClick", "frontend")

def main():
    print(f"[*] Project Root: {ROOT_DIR}")
    
    processes = []
    
    try:
        # 1. Start Backend (FastAPI)
        print("[*] Starting Backend (FastAPI)...")
        # Use shell=True to allow running command strings on Windows
        backend = subprocess.Popen(
            "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000", 
            cwd=BACKEND_DIR,
            shell=True
        )
        processes.append(backend)
        
        # Wait a few seconds for backend to initialize
        time.sleep(2)

        # 2. Start Frontend (Vite)
        print("[*] Starting Frontend (Vite)...")
        frontend = subprocess.Popen(
            "npm run dev", 
            cwd=FRONTEND_DIR,
            shell=True
        )
        processes.append(frontend)

        print("\n" + "="*60)
        print("   SYSTEM RUNNING - PRESS CTRL+C TO STOP ALL SERVICES")
        print("   Backend: http://localhost:8000")
        print("   Frontend: http://localhost:5174")
        print("="*60 + "\n")

        # 3. Auto-open browser
        time.sleep(2)
        try:
            webbrowser.open("http://localhost:5174")
        except:
            pass

        # Keep main process running until user hits Ctrl+C
        while True:
            time.sleep(1)
            # Check if subprocesses exited unexpectedly
            if backend.poll() is not None:
                print("[!] Backend process ended unexpectedly.")
                break
            if frontend.poll() is not None:
                print("[!] Frontend process ended unexpectedly.")
                break

    except KeyboardInterrupt:
        print("\n\n[*] Stopping all services...")
    finally:
        # 4. Force kill all processes
        # On Windows, simple .terminate() often fails to kill the process tree started with shell=True
        # So we use taskkill to force clean up
        for p in processes:
            try:
                # /F force, /T terminate child processes (tree), /PID process ID
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(p.pid)], 
                              stdout=subprocess.DEVNULL, 
                              stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[!] Error killing process {p.pid}: {e}")
        
        print("[*] All services stopped. Goodbye!")

if __name__ == "__main__":
    main()

