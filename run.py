import subprocess
import sys
import os
import signal
import time
import threading

def stream_output(process, prefix):
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                print(f"[{prefix}] {line.strip()}", flush=True)
            else:
                break
    except Exception:
        pass

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    frontend_dir = os.path.join(root_dir, "frontend")
    
    # Check Python executable
    venv_python = os.path.join(backend_dir, "venv", "Scripts", "python.exe")
    python_cmd = venv_python if os.path.exists(venv_python) else sys.executable
    
    backend_env = os.environ.copy()
    backend_env["DATABASE_URL"] = "sqlite:///./test_recoverchain.db"
    backend_env["PYTHONPATH"] = "."
    # This is the local, offline dev launcher — silence the prod-default warnings.
    backend_env.setdefault("ALLOW_INSECURE_DEFAULTS", "1")
    
    print("==================================================", flush=True)
    print("  RECOVERCHAIN AI - UNIFIED APPLICATION LAUNCHER", flush=True)
    print("==================================================", flush=True)
    print("  Frontend UI : http://127.0.0.1:5173", flush=True)
    print("  Backend API : http://127.0.0.1:8000", flush=True)
    print("  Swagger Docs: http://127.0.0.1:8000/docs", flush=True)
    print("==================================================\n", flush=True)
    
    # 1. Start Backend
    backend_proc = subprocess.Popen(
        [python_cmd, "-m", "uvicorn", "api.main:app", "--port", "8000", "--host", "127.0.0.1"],
        cwd=backend_dir,
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # 2. Start Frontend
    npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
    frontend_proc = subprocess.Popen(
        [npx_cmd, "vite", "--port", "5173", "--host", "127.0.0.1"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Start stream threads
    t_backend = threading.Thread(target=stream_output, args=(backend_proc, "BACKEND"), daemon=True)
    t_frontend = threading.Thread(target=stream_output, args=(frontend_proc, "FRONTEND"), daemon=True)
    t_backend.start()
    t_frontend.start()
    
    def shutdown(signum=None, frame=None):
        print("\nShutting down RecoverChain AI services...", flush=True)
        try:
            backend_proc.terminate()
            frontend_proc.terminate()
            backend_proc.wait(timeout=3)
            frontend_proc.wait(timeout=3)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
        print("All services stopped.", flush=True)
        sys.exit(0)
        
    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)
        
    try:
        while True:
            time.sleep(1)
            b_code = backend_proc.poll()
            f_code = frontend_proc.poll()
            if b_code is not None:
                print(f"[BACKEND] Process exited with code {b_code}", flush=True)
                break
            if f_code is not None:
                print(f"[FRONTEND] Process exited with code {f_code}", flush=True)
                break
    except KeyboardInterrupt:
        shutdown()

if __name__ == "__main__":
    main()
