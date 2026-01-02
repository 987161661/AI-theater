import sys
import subprocess
import time
import os

def main():
    """
    Wrapper script to run uvicorn with crash logging.
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, "-m", "uvicorn", "chat_server:app", "--host", "0.0.0.0", "--port", "8000"]
    
    print(f"[BackendWrapper] Starting: {' '.join(cmd)}")
    
    # Open a crash log file
    log_file = os.path.join(project_root, "backend_service.log")
    
    try:
        # Run uvicorn. 
        # We don't capture output here so it still goes to the main console,
        # but we check the return code.
        proc = subprocess.Popen(cmd, cwd=project_root)
        proc.wait()
        
        if proc.returncode != 0:
            msg = f"[{time.ctime()}] Backend exited with code {proc.returncode}\n"
            print(f"[BackendWrapper] {msg}")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(msg)
                
    except KeyboardInterrupt:
        print("[BackendWrapper] Interrupted by user.")
    except Exception as e:
        msg = f"[{time.ctime()}] Wrapper Exception: {e}\n"
        print(f"[BackendWrapper] {msg}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg)

if __name__ == "__main__":
    main()