from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np
import os
import shutil
import tempfile
from pathlib import Path
import json
import time
import hashlib
from interpreter import interpreter
from dotenv import load_dotenv
import io
import sys
import traceback
from functools import wraps
import threading
import queue

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Analyze & Excel API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
INPUT_FOLDERS = ["input_folder_1", "input_folder_2", "input_folder_3"]
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"

# Create necessary directories
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory storage for analysis tasks
analysis_tasks = {}

# Pydantic models
class AnalysisRequest(BaseModel):
    prompt: str
    file_paths: List[str]
    timeout_seconds: Optional[int] = 300

class AnalysisResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None

class PreviewFilesRequest(BaseModel):
    file_paths: List[str]

# Helper functions
def load_api_key():
    """Load API key from environment"""
    return os.getenv("OPENAI_API_KEY")

def read_excel_or_csv(file_path: str):
    """Read Excel or CSV file into DataFrame or dict of DataFrames"""
    if file_path.endswith('.txt'):
        return pd.DataFrame()
    
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        else:
            excel_file = pd.ExcelFile(file_path)
            sheets_dict = {}
            for sheet_name in excel_file.sheet_names:
                sheets_dict[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
            return sheets_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading {file_path}: {str(e)}")

def get_file_context(file_paths: List[str]) -> str:
    """Create context string from file paths"""
    context = "Available files:\n"
    for file_path in file_paths:
        try:
            if file_path.endswith('.txt'):
                context += f"\n- {os.path.basename(file_path)}: Text file\n"
                continue
            
            data = read_excel_or_csv(file_path)
            if isinstance(data, dict):
                context += f"\n- {os.path.basename(file_path)}: Excel file with {len(data)} sheet(s)\n"
                for sheet_name, df in data.items():
                    if not df.empty:
                        context += f"  Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns\n"
                        context += f"    Columns: {', '.join(df.columns.tolist())}\n"
            elif isinstance(data, pd.DataFrame):
                if not data.empty:
                    context += f"\n- {os.path.basename(file_path)}: {len(data)} rows, {len(data.columns)} columns\n"
                    context += f"  Columns: {', '.join(data.columns.tolist())}\n"
        except Exception as e:
            context += f"\n- {os.path.basename(file_path)}: Error reading file - {str(e)}\n"
    return context

def get_existing_output_files(output_folder: str) -> set:
    """Get set of existing output files before execution"""
    existing_files = set()
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            if file.endswith(('.xlsx', '.xls', '.csv', '.txt')):
                existing_files.add(os.path.join(output_folder, file))
    return existing_files

def timeout_handler(timeout_seconds: int):
    """Decorator to add timeout to a function call"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)
            
            if thread.is_alive():
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator

def run_analysis(prompt: str, file_paths: List[str], output_folder: str, timeout_seconds: int, task_id: str):
    """Run analysis in background"""
    try:
        analysis_tasks[task_id]["status"] = "running"
        analysis_tasks[task_id]["progress"] = 0.1
        
        api_key = load_api_key()
        if not api_key:
            raise Exception("OpenAI API key not found")
        
        existing_files = get_existing_output_files(output_folder)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        summary_filename = f"summary_{timestamp}_{prompt_hash}.txt"
        summary_filepath = os.path.join(output_folder, summary_filename)
        
        interpreter.api_key = api_key
        interpreter.auto_run = True
        interpreter.verbose = False
        
        file_context = get_file_context(file_paths)
        file_paths_str = "\n".join([f"  - {fp}" for fp in file_paths])
        
        system_context = f"""You are an expert data analyst working with Excel and CSV files.

Available files:
{file_context}

File paths (use these exact paths in your code):
{file_paths_str}

Output folder: {output_folder}

IMPORTANT INSTRUCTIONS:
1. When reading files, use the exact file paths provided above
2. When saving results, save to: {output_folder}
3. Use pandas (pd.read_excel, pd.read_csv) to read files
4. Use df.to_excel() or df.to_csv() to save results
5. Always use index=False when saving Excel files
6. Provide clear explanations of what you're doing
7. Answer in Russian

CRITICAL RESTRICTIONS:
- DO NOT create HTML files (df.to_html() is FORBIDDEN)
- DO NOT use webbrowser.open() or any function that opens files in a browser
- DO NOT use os.startfile() or subprocess to open files
- When displaying dataframes, use print() or df.head() instead of creating HTML files
- Save results ONLY as Excel (.xlsx) or CSV (.csv) files, NEVER as HTML

CRITICAL: You MUST create a summary file at the end of your analysis!
8. At the end of your analysis, you MUST write a summary file to: '{summary_filepath}'
9. Use this EXACT code to create the summary file:
   with open(r'{summary_filepath}', 'w', encoding='utf-8') as f:
       f.write('Your summary content here with main findings, analysis results, and key insights')
10. The summary should contain:
   - Main findings from the analysis
   - Key insights and patterns discovered
   - Important conclusions
   - Any significant trends or changes identified
11. DO NOT skip creating this summary file - it is required!"""
        
        analysis_tasks[task_id]["progress"] = 0.3
        
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        
        @timeout_handler(timeout_seconds)
        def run_interpreter():
            sys.stdout = output_buffer
            try:
                if hasattr(interpreter, 'reset'):
                    interpreter.reset()
                result = interpreter.chat(f"{system_context}\n\nUser request: {prompt}")
                return result
            finally:
                sys.stdout = old_stdout
        
        analysis_tasks[task_id]["progress"] = 0.5
        
        run_interpreter()
        response_text = output_buffer.getvalue()
        sys.stdout = old_stdout
        
        analysis_tasks[task_id]["progress"] = 0.8
        
        # Check for newly generated files
        generated_files = []
        current_files = get_existing_output_files(output_folder)
        for file_path in current_files:
            if file_path not in existing_files:
                generated_files.append(file_path)
        
        # Read summary file
        main_answer = ""
        if os.path.exists(summary_filepath):
            with open(summary_filepath, "r", encoding="utf-8") as f:
                main_answer = f.read().strip()
        
        if not main_answer:
            main_answer = "Analysis completed. Please check the generated files for results."
            if generated_files:
                main_answer += f"\n\nGenerated files: {', '.join([os.path.basename(f) for f in generated_files])}"
        
        analysis_tasks[task_id]["status"] = "completed"
        analysis_tasks[task_id]["progress"] = 1.0
        analysis_tasks[task_id]["result"] = {
            "main_answer": main_answer,
            "intermediate_steps": response_text,
            "generated_files": generated_files,
            "answer_file": summary_filepath if os.path.exists(summary_filepath) else None
        }
        
    except TimeoutError as e:
        analysis_tasks[task_id]["status"] = "error"
        analysis_tasks[task_id]["error"] = str(e)
    except Exception as e:
        analysis_tasks[task_id]["status"] = "error"
        analysis_tasks[task_id]["error"] = f"Error during execution: {str(e)}\n{traceback.format_exc()}"

# API Routes
@app.get("/")
async def root():
    return {"message": "Analyze & Excel API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/folders")
async def get_folders():
    """Get list of available input folders"""
    available = []
    for folder in INPUT_FOLDERS:
        if os.path.exists(folder) and os.path.isdir(folder):
            files = []
            for file in os.listdir(folder):
                if file.endswith(('.xlsx', '.xls', '.csv')):
                    files.append({
                        "name": file,
                        "path": os.path.join(folder, file)
                    })
            available.append({
                "name": folder,
                "files": files
            })
    return {"folders": available}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file info
        file_info = {
            "name": file.filename,
            "path": file_path,
            "size": os.path.getsize(file_path)
        }
        
        # Try to read file to get structure info
        try:
            data = read_excel_or_csv(file_path)
            if isinstance(data, dict):
                file_info["type"] = "excel"
                file_info["sheets"] = list(data.keys())
            elif isinstance(data, pd.DataFrame):
                file_info["type"] = "csv" if file_path.endswith('.csv') else "excel"
                file_info["rows"] = len(data)
                file_info["columns"] = len(data.columns)
        except:
            pass
        
        return {"message": "File uploaded successfully", "file": file_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
async def list_files():
    """List all uploaded files and files from input folders"""
    files = []
    
    # Get files from uploads
    if os.path.exists(UPLOAD_FOLDER):
        for file in os.listdir(UPLOAD_FOLDER):
            if file.endswith(('.xlsx', '.xls', '.csv')):
                files.append({
                    "name": file,
                    "path": os.path.join(UPLOAD_FOLDER, file),
                    "source": "upload"
                })
    
    # Get files from input folders
    for folder in INPUT_FOLDERS:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.endswith(('.xlsx', '.xls', '.csv')):
                    files.append({
                        "name": file,
                        "path": os.path.join(folder, file),
                        "source": folder
                    })
    
    return {"files": files}

def clean_dataframe_for_json(df: pd.DataFrame) -> list:
    """Convert DataFrame to JSON-compliant list of dicts, replacing NaN/Inf with None"""
    if df.empty:
        return []
    
    # Make a copy to avoid modifying the original
    df_cleaned = df.copy()
    
    # Replace Infinity and -Infinity with None
    df_cleaned = df_cleaned.replace([float('inf'), float('-inf')], None)
    
    # Replace NaN, NaT, and other null values with None using where() method
    # This is more reliable than fillna() for converting to None
    df_cleaned = df_cleaned.where(pd.notnull(df_cleaned), None)
    
    # Convert to dict - pandas will convert numpy types to native Python types
    result = df_cleaned.to_dict(orient="records")
    
    # Final pass: ensure all values are JSON-serializable
    # Convert any remaining non-serializable values
    def make_json_serializable(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item() if not (np.isnan(obj) or np.isinf(obj)) else None
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return obj
    
    # Recursively clean the result
    cleaned_result = []
    for record in result:
        cleaned_record = {}
        for key, value in record.items():
            cleaned_record[key] = make_json_serializable(value)
        cleaned_result.append(cleaned_record)
    
    return cleaned_result

@app.get("/api/files/{file_path:path}/preview")
async def preview_file(file_path: str):
    """Preview file data"""
    try:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        data = read_excel_or_csv(file_path)
        
        if isinstance(data, dict):
            # Multi-sheet Excel
            preview = {}
            for sheet_name, df in data.items():
                preview[sheet_name] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": df.columns.tolist(),
                    "preview": clean_dataframe_for_json(df.head(1000))  # Show up to 1000 rows
                }
            return {"type": "excel", "sheets": preview}
        elif isinstance(data, pd.DataFrame):
            return {
                "type": "csv" if file_path.endswith('.csv') else "excel",
                "rows": len(data),
                "columns": len(data.columns),
                "column_names": data.columns.tolist(),
                "preview": clean_dataframe_for_json(data.head(1000))  # Show up to 1000 rows
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/preview")
async def preview_files(request: PreviewFilesRequest):
    """Preview multiple files at once - returns preview data for all files"""
    try:
        result = {}
        
        for file_path in request.file_paths:
            if not os.path.exists(file_path):
                result[file_path] = {
                    "error": "File not found",
                    "file_name": os.path.basename(file_path)
                }
                continue
            
            try:
                data = read_excel_or_csv(file_path)
                
                if isinstance(data, dict):
                    # Multi-sheet Excel
                    preview = {}
                    for sheet_name, df in data.items():
                        preview[sheet_name] = {
                            "rows": len(df),
                            "columns": len(df.columns),
                            "column_names": df.columns.tolist(),
                            "preview": clean_dataframe_for_json(df.head(1000))  # Show up to 1000 rows
                        }
                    result[file_path] = {
                        "type": "excel",
                        "file_name": os.path.basename(file_path),
                        "sheets": preview
                    }
                elif isinstance(data, pd.DataFrame):
                    result[file_path] = {
                        "type": "csv" if file_path.endswith('.csv') else "excel",
                        "file_name": os.path.basename(file_path),
                        "rows": len(data),
                        "columns": len(data.columns),
                        "column_names": data.columns.tolist(),
                        "preview": clean_dataframe_for_json(data.head(1000))  # Show up to 1000 rows
                    }
            except Exception as e:
                result[file_path] = {
                    "error": str(e),
                    "file_name": os.path.basename(file_path)
                }
        
        return {"files": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_files(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """Start analysis task"""
    api_key = load_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not found")
    
    # Validate file paths
    for file_path in request.file_paths:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    # Generate task ID
    task_id = hashlib.md5(f"{request.prompt}{time.time()}".encode()).hexdigest()[:12]
    
    # Initialize task
    analysis_tasks[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "prompt": request.prompt,
        "file_paths": request.file_paths
    }
    
    # Start background task
    background_tasks.add_task(
        run_analysis,
        request.prompt,
        request.file_paths,
        OUTPUT_FOLDER,
        request.timeout_seconds or 300,
        task_id
    )
    
    return {"task_id": task_id, "status": "pending", "message": "Analysis started"}

@app.post("/api/analyze/stream")
async def analyze_files_stream(request: AnalysisRequest):
    """Start analysis task with streaming responses"""
    api_key = load_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not found")
    
    # Validate file paths
    for file_path in request.file_paths:
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    async def generate_stream():
        """Generator function for Server-Sent Events"""
        try:
            # Generate task ID
            task_id = hashlib.md5(f"{request.prompt}{time.time()}".encode()).hexdigest()[:12]
            
            # Initialize task
            analysis_tasks[task_id] = {
                "status": "running",
                "progress": 0.0,
                "prompt": request.prompt,
                "file_paths": request.file_paths
            }
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'task_id': task_id, 'status': 'running', 'progress': 0.0})}\n\n"
            
            # Get existing files
            existing_files = get_existing_output_files(OUTPUT_FOLDER)
            
            # Generate summary filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            prompt_hash = hashlib.md5(request.prompt.encode()).hexdigest()[:8]
            summary_filename = f"summary_{timestamp}_{prompt_hash}.txt"
            summary_filepath = os.path.join(OUTPUT_FOLDER, summary_filename)
            
            # Configure interpreter
            interpreter.api_key = api_key
            interpreter.auto_run = True
            interpreter.verbose = False
            
            # Create context
            file_context = get_file_context(request.file_paths)
            file_paths_str = "\n".join([f"  - {fp}" for fp in request.file_paths])
            
            system_context = f"""You are an expert data analyst working with Excel and CSV files.

Available files:
{file_context}

File paths (use these exact paths in your code):
{file_paths_str}

Output folder: {OUTPUT_FOLDER}

IMPORTANT INSTRUCTIONS:
1. When reading files, use the exact file paths provided above
2. When saving results, save to: {OUTPUT_FOLDER}
3. Use pandas (pd.read_excel, pd.read_csv) to read files
4. Use df.to_excel() or df.to_csv() to save results
5. Always use index=False when saving Excel files
6. Provide clear explanations of what you're doing
7. Answer in Russian

CRITICAL RESTRICTIONS:
- DO NOT create HTML files (df.to_html() is FORBIDDEN)
- DO NOT use webbrowser.open() or any function that opens files in a browser
- DO NOT use os.startfile() or subprocess to open files
- When displaying dataframes, use print() or df.head() instead of creating HTML files
- Save results ONLY as Excel (.xlsx) or CSV (.csv) files, NEVER as HTML

CRITICAL: You MUST create a summary file at the end of your analysis!
8. At the end of your analysis, you MUST write a summary file to: '{summary_filepath}'
9. Use this EXACT code to create the summary file:
   with open(r'{summary_filepath}', 'w', encoding='utf-8') as f:
       f.write('Your summary content here with main findings, analysis results, and key insights')
10. The summary should contain:
   - Main findings from the analysis
   - Key insights and patterns discovered
   - Important conclusions
   - Any significant trends or changes identified
11. DO NOT skip creating this summary file - it is required!"""
            
            # Create a queue for streaming output
            output_queue = queue.Queue()
            output_buffer = io.StringIO()
            old_stdout = sys.stdout
            captured_output = []
            
            # Custom stdout that captures and queues output
            class StreamingStdout:
                def __init__(self, original_stdout, queue, buffer):
                    self.original_stdout = original_stdout
                    self.queue = queue
                    self.buffer = buffer
                
                def write(self, text):
                    if text:
                        self.buffer.write(text)
                        self.queue.put(text)
                        captured_output.append(text)
                
                def flush(self):
                    self.original_stdout.flush()
            
            streaming_stdout = StreamingStdout(old_stdout, output_queue, output_buffer)
            sys.stdout = streaming_stdout
            
            # Intercept functions that open windows
            import webbrowser
            import subprocess
            
            original_webbrowser_open = webbrowser.open
            original_startfile = None
            if hasattr(os, 'startfile'):
                original_startfile = os.startfile
            original_subprocess_call = subprocess.call
            original_subprocess_Popen = subprocess.Popen
            
            def intercepted_webbrowser_open(url, new=0, autoraise=True):
                """Intercept webbrowser.open() calls and capture the URL instead"""
                message = f"[Intercepted webbrowser.open() call - URL: {url}]\n"
                message += "Note: Browser windows are disabled. Data is captured in the output instead.\n"
                output_queue.put(message)
                output_buffer.write(message)
                return False  # Don't actually open
            
            def intercepted_startfile(filepath, operation='open'):
                """Intercept os.startfile() calls and capture the file path instead"""
                message = f"[Intercepted os.startfile() call - File: {filepath}, Operation: {operation}]\n"
                message += "Note: File opening is disabled. Please use the preview/download buttons instead.\n"
                output_queue.put(message)
                output_buffer.write(message)
                return None  # Don't actually open
            
            def intercepted_subprocess_call(*args, **kwargs):
                """Intercept subprocess.call() that might open files"""
                # Check if it's trying to open a file
                if args and len(args) > 0:
                    cmd = args[0]
                    if isinstance(cmd, (list, tuple)) and len(cmd) > 0:
                        cmd_str = str(cmd[0]).lower()
                        # Common commands that open files
                        if any(x in cmd_str for x in ['start', 'open', 'xdg-open', 'see']):
                            message = f"[Intercepted subprocess.call() that would open file: {cmd}]\n"
                            message += "Note: File opening is disabled. Please use the preview/download buttons instead.\n"
                            output_queue.put(message)
                            output_buffer.write(message)
                            return 0  # Return success but don't actually open
                # For other subprocess calls, allow them but log
                return original_subprocess_call(*args, **kwargs)
            
            # Patch pandas DataFrame to_html to prevent HTML file creation
            original_to_html = None
            if hasattr(pd.DataFrame, 'to_html'):
                original_to_html = pd.DataFrame.to_html
                
                def intercepted_to_html(self, *args, **kwargs):
                    """Intercept DataFrame.to_html() calls"""
                    message = "[Intercepted DataFrame.to_html() call]\n"
                    message += "Note: HTML file creation is disabled. Use print(df) or df.head() to display data instead.\n"
                    output_queue.put(message)
                    output_buffer.write(message)
                    # Return empty string instead of HTML
                    return ""
                
                pd.DataFrame.to_html = intercepted_to_html
            
            # Patch the functions
            webbrowser.open = intercepted_webbrowser_open
            if original_startfile:
                os.startfile = intercepted_startfile
            subprocess.call = intercepted_subprocess_call
            
            # Update progress
            analysis_tasks[task_id]["progress"] = 0.3
            yield f"data: {json.dumps({'type': 'progress', 'progress': 0.3})}\n\n"
            
            # Run interpreter in a thread
            interpreter_result = [None]
            interpreter_error = [None]
            
            # Store original_to_html in outer scope for restoration
            original_to_html_outer = original_to_html
            
            def run_interpreter_thread():
                try:
                    if hasattr(interpreter, 'reset'):
                        interpreter.reset()
                    
                    # Try to use streaming if available
                    if hasattr(interpreter, 'chat_stream'):
                        # Use streaming chat if available
                        for chunk in interpreter.chat_stream(f"{system_context}\n\nUser request: {request.prompt}"):
                            if chunk:
                                output_queue.put(f"data: {json.dumps({'type': 'chunk', 'content': str(chunk)})}\n\n")
                    else:
                        # Fallback to regular chat
                        result = interpreter.chat(f"{system_context}\n\nUser request: {request.prompt}")
                        interpreter_result[0] = result
                except Exception as e:
                    interpreter_error[0] = e
                finally:
                    sys.stdout = old_stdout
                    # Restore original functions
                    try:
                        webbrowser.open = original_webbrowser_open
                        if original_startfile:
                            os.startfile = original_startfile
                        subprocess.call = original_subprocess_call
                        subprocess.Popen = original_subprocess_Popen
                        if original_to_html_outer:
                            pd.DataFrame.to_html = original_to_html_outer
                    except:
                        pass
                    output_queue.put(None)  # Signal completion
            
            # Start interpreter thread
            interpreter_thread = threading.Thread(target=run_interpreter_thread, daemon=True)
            interpreter_thread.start()
            
            # Stream output while interpreter is running
            last_output_time = time.time()
            while interpreter_thread.is_alive() or not output_queue.empty():
                try:
                    # Get output with timeout
                    chunk = output_queue.get(timeout=0.5)
                    if chunk is None:
                        break
                    # Format as SSE message
                    yield f"data: {json.dumps({'type': 'output', 'content': chunk})}\n\n"
                    last_output_time = time.time()
                except queue.Empty:
                    # Check if thread is still alive
                    if not interpreter_thread.is_alive():
                        break
                    # Send heartbeat
                    if time.time() - last_output_time > 5:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                        last_output_time = time.time()
            
            # Wait for thread to complete
            interpreter_thread.join(timeout=1)
            
            # Check for errors
            if interpreter_error[0]:
                raise interpreter_error[0]
            
            # Get final output
            response_text = output_buffer.getvalue()
            sys.stdout = old_stdout
            
            # Restore original functions
            try:
                webbrowser.open = original_webbrowser_open
                if original_startfile:
                    os.startfile = original_startfile
                subprocess.call = original_subprocess_call
                subprocess.Popen = original_subprocess_Popen
                if original_to_html_outer:
                    pd.DataFrame.to_html = original_to_html_outer
            except:
                pass
            
            # Update progress
            analysis_tasks[task_id]["progress"] = 0.8
            yield f"data: {json.dumps({'type': 'progress', 'progress': 0.8})}\n\n"
            
            # Check for newly generated files
            generated_files = []
            current_files = get_existing_output_files(OUTPUT_FOLDER)
            for file_path in current_files:
                if file_path not in existing_files:
                    generated_files.append(file_path)
            
            # Read summary file
            main_answer = ""
            if os.path.exists(summary_filepath):
                with open(summary_filepath, "r", encoding="utf-8") as f:
                    main_answer = f.read().strip()
            
            if not main_answer:
                main_answer = "Analysis completed. Please check the generated files for results."
                if generated_files:
                    main_answer += f"\n\nGenerated files: {', '.join([os.path.basename(f) for f in generated_files])}"
            
            # Update task status
            analysis_tasks[task_id]["status"] = "completed"
            analysis_tasks[task_id]["progress"] = 1.0
            analysis_tasks[task_id]["result"] = {
                "main_answer": main_answer,
                "intermediate_steps": response_text,
                "generated_files": generated_files,
                "answer_file": summary_filepath if os.path.exists(summary_filepath) else None
            }
            
            # Send final result
            yield f"data: {json.dumps({'type': 'result', 'result': analysis_tasks[task_id]['result']})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'status': 'completed', 'progress': 1.0})}\n\n"
            
        except TimeoutError as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            if task_id in analysis_tasks:
                analysis_tasks[task_id]["status"] = "error"
                analysis_tasks[task_id]["error"] = error_msg
        except Exception as e:
            error_msg = f"Error during execution: {str(e)}\n{traceback.format_exc()}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            if task_id in analysis_tasks:
                analysis_tasks[task_id]["status"] = "error"
                analysis_tasks[task_id]["error"] = error_msg
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get analysis task status"""
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = analysis_tasks[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0.0),
        "result": task.get("result"),
        "error": task.get("error")
    }

@app.get("/api/output")
async def list_output_files():
    """List all output files"""
    files = []
    if os.path.exists(OUTPUT_FOLDER):
        for file in os.listdir(OUTPUT_FOLDER):
            if file.endswith(('.xlsx', '.xls', '.csv', '.txt')):
                file_path = os.path.join(OUTPUT_FOLDER, file)
                files.append({
                    "name": file,
                    "path": file_path,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
    return {"files": sorted(files, key=lambda x: x["modified"], reverse=True)}

@app.get("/api/download/{file_path:path}")
async def download_file(file_path: str):
    """Download a file"""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Security check - ensure file is in allowed directories
    if not (file_path.startswith(OUTPUT_FOLDER) or 
            file_path.startswith(UPLOAD_FOLDER) or
            any(file_path.startswith(folder) for folder in INPUT_FOLDERS)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=os.path.basename(file_path)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

