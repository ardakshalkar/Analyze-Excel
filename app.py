import streamlit as st
import pandas as pd
import os
from interpreter import interpreter
from pathlib import Path
import tempfile
import shutil
from typing import List, Optional
import json
import io
import traceback
import sys
import time
import hashlib
import threading
from functools import wraps
import plotly.express as px
import plotly.graph_objects as go

# Check Streamlit version for st.dialog support
try:
    streamlit_version = st.__version__
    version_parts = [int(x) for x in streamlit_version.split('.')]
    if version_parts[0] < 1 or (version_parts[0] == 1 and version_parts[1] < 29):
        st.error(f"⚠️ **Streamlit version {streamlit_version} is too old!**")
        st.error("`st.dialog` requires Streamlit >= 1.29.0")
        st.info("**To upgrade, run:** `pip install --upgrade streamlit>=1.29.0`")
        st.stop()
    
    # Verify st.dialog exists
    if not hasattr(st, 'dialog'):
        st.error("⚠️ **`st.dialog` is not available in this Streamlit installation.**")
        st.info("**To upgrade, run:** `pip install --upgrade streamlit>=1.29.0`")
        st.info("**Then restart your Streamlit app.**")
        st.stop()
except Exception as e:
    st.warning(f"Could not verify Streamlit version: {e}")
    if not hasattr(st, 'dialog'):
        st.error("⚠️ **`st.dialog` is not available.**")
        st.info("**To upgrade, run:** `pip install --upgrade streamlit>=1.29.0`")
        st.stop()

# Page configuration
st.set_page_config(
    page_title="Analyze & Excel",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'output_files' not in st.session_state:
    st.session_state.output_files = []
if 'processed_dataframes' not in st.session_state:
    st.session_state.processed_dataframes = {}
if 'selected_sheets' not in st.session_state:
    st.session_state.selected_sheets = {}  # {file_path: sheet_name}
if 'active_tab_index' not in st.session_state:
    st.session_state.active_tab_index = {}
if 'selected_folder_files' not in st.session_state:
    st.session_state.selected_folder_files = {}  # {folder_name: [file_paths]}
if 'uploaded_file_paths' not in st.session_state:
    st.session_state.uploaded_file_paths = []  # List of uploaded file paths

# Constants
INPUT_FOLDERS = ["input_folder_1", "input_folder_2", "input_folder_3"]  # Predefined folder names
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"

# Create necessary directories
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load OpenAI API key
def load_api_key():
    """Load API key from environment or .env file only"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Only check environment variable
    env_key = os.getenv("OPENAI_API_KEY")
    return env_key

# Load timeout from environment
def load_timeout():
    """Load timeout from environment variable or use default"""
    from dotenv import load_dotenv
    load_dotenv()
    
    timeout_str = os.getenv("TIMEOUT_SECONDS")
    if timeout_str:
        try:
            return int(timeout_str)
        except ValueError:
            pass
    
    # Default: 5 minutes (300 seconds)
    return 300

def get_available_folders():
    """Get list of available predefined folders"""
    available = []
    for folder in INPUT_FOLDERS:
        if os.path.exists(folder) and os.path.isdir(folder):
            available.append(folder)
    return available

def load_files_from_folder(folder_path: str) -> List[str]:
    """Load Excel and CSV files from a folder"""
    files = []
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            if file.endswith(('.xlsx', '.xls', '.csv')):
                files.append(os.path.join(folder_path, file))
    return files

def process_uploaded_file(uploaded_file) -> str:
    """Save uploaded file to upload folder and return path"""
    file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def read_excel_or_csv(file_path: str):
    """Read Excel or CSV file into DataFrame or dict of DataFrames (for multi-sheet Excel files)
    Returns:
        - For CSV: pd.DataFrame
        - For Excel: dict[str, pd.DataFrame] where keys are sheet names
    """
    # Skip text files
    if file_path.endswith('.txt'):
        return pd.DataFrame()
    
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        else:
            # Read all sheets from Excel file
            excel_file = pd.ExcelFile(file_path)
            sheets_dict = {}
            for sheet_name in excel_file.sheet_names:
                sheets_dict[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
            return sheets_dict
    except Exception as e:
        st.error(f"Error reading {file_path}: {str(e)}")
        return pd.DataFrame() if file_path.endswith('.csv') else {}

def get_file_context(file_paths: List[str]) -> str:
    """Create context string from file paths for the prompt"""
    context = "Available files:\n"
    for file_path in file_paths:
        try:
            # Skip text files in context (they're output files, not input files)
            if file_path.endswith('.txt'):
                context += f"\n- {os.path.basename(file_path)}: Text file\n"
                continue
            
            data = read_excel_or_csv(file_path)
            if isinstance(data, dict):
                # Excel file with multiple sheets
                context += f"\n- {os.path.basename(file_path)}: Excel file with {len(data)} sheet(s)\n"
                for sheet_name, df in data.items():
                    if not df.empty:
                        context += f"  Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns\n"
                        context += f"    Columns: {', '.join(df.columns.tolist())}\n"
            elif isinstance(data, pd.DataFrame):
                # CSV or single sheet
                if not data.empty:
                    context += f"\n- {os.path.basename(file_path)}: {len(data)} rows, {len(data.columns)} columns\n"
                    context += f"  Columns: {', '.join(data.columns.tolist())}\n"
                else:
                    context += f"\n- {os.path.basename(file_path)}: Empty or unsupported file\n"
            else:
                context += f"\n- {os.path.basename(file_path)}: Empty or unsupported file\n"
        except Exception as e:
            context += f"\n- {os.path.basename(file_path)}: Error reading file - {str(e)}\n"
    return context

def get_current_dataframe(file_path: str):
    """Get the current dataframe for a file, handling multi-sheet Excel files"""
    if file_path not in st.session_state.processed_dataframes:
        return None
    
    data = st.session_state.processed_dataframes[file_path]
    
    if isinstance(data, dict):
        # Multi-sheet Excel file - get selected sheet
        selected_sheet = st.session_state.selected_sheets.get(file_path)
        if selected_sheet and selected_sheet in data:
            return data[selected_sheet]
        elif data:
            # Fallback to first sheet
            return list(data.values())[0]
        return None
    elif isinstance(data, pd.DataFrame):
        # Single dataframe (CSV or single sheet)
        return data
    
    return None

def get_sheet_names(file_path: str) -> list:
    """Get list of sheet names for a file (empty list for CSV or single sheet)"""
    if file_path not in st.session_state.processed_dataframes:
        return []
    
    data = st.session_state.processed_dataframes[file_path]
    if isinstance(data, dict):
        return list(data.keys())
    return []

def show_file_preview_modal(file_path: str):
    """Show file preview in a modal with data, statistics, and visualizations"""
    # Check if file exists
    if not os.path.exists(file_path):
        st.error(f"File not found: {os.path.basename(file_path)}")
        return
    
    # Skip text files
    if file_path.endswith('.txt'):
        st.info("Text files cannot be previewed in this view. Please download the file to view its contents.")
        return
    
    # Load the file if not already loaded
    try:
        if file_path not in st.session_state.processed_dataframes:
            data = read_excel_or_csv(file_path)
            if isinstance(data, dict):
                st.session_state.processed_dataframes[file_path] = data
                if file_path not in st.session_state.selected_sheets:
                    st.session_state.selected_sheets[file_path] = list(data.keys())[0] if data else None
            elif isinstance(data, pd.DataFrame) and not data.empty:
                st.session_state.processed_dataframes[file_path] = data
        
        # Get the dataframe
        df = get_current_dataframe(file_path)
        
        if df is None or df.empty:
            st.error("Could not load file or file is empty.")
            return
    except Exception as e:
        st.error(f"Error loading file: {str(e)}")
        return
    
    # File info
    st.markdown(f"### 📄 {os.path.basename(file_path)}")
    
    # Basic info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Rows", len(df))
    with col2:
        st.metric("Total Columns", len(df.columns))
    with col3:
        file_size = os.path.getsize(file_path) / 1024
        st.metric("File Size", f"{file_size:.2f} KB")
    with col4:
        st.metric("Preview Rows", min(100, len(df)))
    
    # Sheet selection for multi-sheet Excel files
    sheet_names = get_sheet_names(file_path)
    if sheet_names and len(sheet_names) > 1:
        current_sheet = st.session_state.selected_sheets.get(file_path, sheet_names[0])
        if current_sheet not in sheet_names:
            current_sheet = sheet_names[0]
        selected_sheet = st.selectbox(
            "Select Sheet:",
            sheet_names,
            index=sheet_names.index(current_sheet),
            key=f"preview_sheet_{file_path}"
        )
        st.session_state.selected_sheets[file_path] = selected_sheet
        df = get_current_dataframe(file_path)
    
    st.markdown("---")
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Preview (First 100)", "📈 Statistics", "📉 Visualizations", "ℹ️ Data Info"])
    
    with tab1:
        st.markdown("**First 100 rows:**")
        preview_df = df.head(100)
        st.dataframe(preview_df, use_container_width=True, height=400)
        if len(df) > 100:
            st.info(f"Showing first 100 of {len(df)} total rows.")
    
    with tab2:
        st.markdown("**Statistical Summary:**")
        if len(df.select_dtypes(include=['number']).columns) > 0:
            st.dataframe(df.describe(), use_container_width=True)
        else:
            st.info("No numeric columns found for statistical summary.")
        
        st.markdown("**Missing Values:**")
        missing_data = df.isnull().sum()
        missing_df = pd.DataFrame({
            'Column': missing_data.index,
            'Missing Count': missing_data.values,
            'Missing %': (missing_data.values / len(df) * 100).round(2)
        })
        missing_df = missing_df[missing_df['Missing Count'] > 0]
        if len(missing_df) > 0:
            st.dataframe(missing_df, use_container_width=True)
        else:
            st.success("✅ No missing values found!")
    
    with tab3:
        st.markdown("**Data Visualizations:**")
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if len(numeric_cols) == 0:
            st.info("No numeric columns found for visualization.")
        else:
            # Distribution plots for numeric columns
            if len(numeric_cols) > 0:
                selected_col = st.selectbox("Select column for distribution:", numeric_cols, key=f"dist_col_{file_path}")
                if selected_col:
                    try:
                        fig = px.histogram(df, x=selected_col, title=f"Distribution of {selected_col}")
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not create histogram: {str(e)}")
            
            # Correlation heatmap if multiple numeric columns
            if len(numeric_cols) > 1:
                st.markdown("**Correlation Matrix:**")
                try:
                    corr_matrix = df[numeric_cols].corr()
                    fig = px.imshow(
                        corr_matrix,
                        labels=dict(x="Columns", y="Columns", color="Correlation"),
                        x=corr_matrix.columns,
                        y=corr_matrix.columns,
                        color_continuous_scale="RdBu",
                        aspect="auto"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.warning(f"Could not create correlation matrix: {str(e)}")
            
            # Box plots for numeric columns
            if len(numeric_cols) > 0:
                st.markdown("**Box Plots:**")
                selected_cols = st.multiselect(
                    "Select columns for box plot:",
                    numeric_cols,
                    default=numeric_cols[:min(5, len(numeric_cols))],
                    key=f"box_cols_{file_path}"
                )
                if selected_cols:
                    try:
                        # Create box plots
                        fig = go.Figure()
                        for col in selected_cols:
                            fig.add_trace(go.Box(y=df[col], name=col))
                        fig.update_layout(title="Box Plots", yaxis_title="Value")
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not create box plots: {str(e)}")
    
    with tab4:
        st.markdown("**Data Types:**")
        dtype_df = pd.DataFrame({
            'Column': df.columns,
            'Data Type': [str(dtype) for dtype in df.dtypes],
            'Non-Null Count': df.count().values,
            'Null Count': df.isnull().sum().values
        })
        st.dataframe(dtype_df, use_container_width=True)
        
        st.markdown("**Memory Usage:**")
        memory_usage = df.memory_usage(deep=True)
        total_memory = memory_usage.sum() / 1024  # KB
        st.info(f"Total memory usage: {total_memory:.2f} KB")

def get_existing_output_files(output_folder: str) -> set:
    """Get set of existing output files before execution"""
    existing_files = set()
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            if file.endswith(('.xlsx', '.xls', '.csv', '.txt')):
                existing_files.add(os.path.join(output_folder, file))
    return existing_files

def save_answer_to_file(answer: str, prompt: str, output_folder: str) -> str:
    """Save the main answer to a text file"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_prompt = "".join(c for c in prompt[:50] if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
    filename = f"answer_{timestamp}_{safe_prompt}.txt"
    file_path = os.path.join(output_folder, filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"Prompt: {prompt}\n")
        f.write("=" * 80 + "\n\n")
        f.write("Answer:\n")
        f.write("=" * 80 + "\n\n")
        f.write(answer)
    
    return file_path

def extract_main_answer(response_text: str) -> str:
    """Extract the main answer from the response, removing intermediate execution details"""
    # Try to find the main answer by looking for patterns
    # This is a simple heuristic - you might want to improve it based on actual output format
    lines = response_text.split('\n')
    main_answer_lines = []
    skip_patterns = ['>', '>>>', '...', 'Running', 'Executing', 'Code:', '```']
    
    in_code_block = False
    for line in lines:
        # Skip code blocks
        if '```' in line:
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        
        # Skip lines that look like execution traces
        stripped = line.strip()
        if any(stripped.startswith(pattern) for pattern in skip_patterns):
            continue
        
        # Include meaningful content
        if stripped and len(stripped) > 10:
            main_answer_lines.append(line)
    
    main_answer = '\n'.join(main_answer_lines)
    
    # If we couldn't extract a good answer, return a cleaned version of the full response
    if not main_answer.strip() or len(main_answer.strip()) < 50:
        # Return a summary or the full response cleaned up
        main_answer = response_text.replace('>>>', '').replace('...', '').strip()
        # Remove excessive blank lines
        lines = main_answer.split('\n')
        cleaned_lines = []
        for i, line in enumerate(lines):
            if line.strip() or (i < len(lines) - 1):
                cleaned_lines.append(line)
        main_answer = '\n'.join(cleaned_lines)
    
    return main_answer.strip()

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
                # Thread is still running, meaning it timed out
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds. The request may be too complex or the files too large. Try simplifying your request or breaking it into smaller tasks.")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator

def call_openai_code_interpreter(prompt: str, file_paths: List[str], output_folder: str, timeout_seconds: int = 300) -> tuple:
    """
    Call Open Interpreter to analyze files and execute code
    Args:
        prompt: User's prompt/request
        file_paths: List of file paths to analyze
        output_folder: Folder to save output files
        timeout_seconds: Maximum time to wait for execution (default: 300 seconds = 5 minutes)
    Returns: (main_answer, intermediate_steps, generated_files, answer_file_path)
    """
    api_key = load_api_key()
    if not api_key:
        error_msg = "Error: OpenAI API key not found. Please set OPENAI_API_KEY in your environment/.env file."
        return error_msg, "", [], None
    
    # Get existing files before execution
    existing_files = get_existing_output_files(output_folder)
    
    # Generate unique summary filename for this request
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    summary_filename = f"summary_{timestamp}_{prompt_hash}.txt"
    summary_filepath = os.path.join(output_folder, summary_filename)
    
    # Configure Open Interpreter
    interpreter.api_key = api_key
    interpreter.auto_run = True  # Automatically execute code
    interpreter.verbose = False   # Reduce output for Streamlit
    # Ensure interpreter completes and doesn't hang
    if hasattr(interpreter, 'max_executions'):
        interpreter.max_executions = 50  # Limit number of code executions to prevent infinite loops
    
    # Create context about available files
    file_context = get_file_context(file_paths)
    file_paths_str = "\n".join([f"  - {fp}" for fp in file_paths])
    
    # Build the system context message
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
    
    try:
        # Create the full prompt with context
        full_prompt = f"{system_context}\n\nUser request: {prompt}"
        
        # Capture stdout to get Open Interpreter's output
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        
        # Define the interpreter chat function with timeout
        @timeout_handler(timeout_seconds)
        def run_interpreter():
            sys.stdout = output_buffer
            try:
                # Reset interpreter to ensure clean state before each run
                if hasattr(interpreter, 'reset'):
                    interpreter.reset()
                
                # Run the interpreter chat - it should return after completing
                # Some versions of open-interpreter may return a value, others don't
                result = interpreter.chat(full_prompt)
                return result
            except Exception as e:
                # Log any exceptions but don't let them stop execution
                print(f"Interpreter error: {str(e)}", file=output_buffer)
                raise
            finally:
                sys.stdout = old_stdout
        
        try:
            # Run interpreter with timeout
            run_interpreter()
            # Get the captured output after execution
            response_text = output_buffer.getvalue()
            
            # Ensure stdout is properly restored
            if sys.stdout != old_stdout:
                sys.stdout = old_stdout
            
        except TimeoutError as e:
            # Restore stdout
            sys.stdout = old_stdout
            error_msg = f"⏱️ Timeout Error: {str(e)}\n\n" + \
                       f"The operation exceeded the time limit of {timeout_seconds} seconds.\n\n" + \
                       "Possible solutions:\n" + \
                       "1. Simplify your request or break it into smaller tasks\n" + \
                       "2. Reduce the size of input files\n" + \
                       "3. Increase the TIMEOUT_SECONDS in your environment/.env file\n" + \
                       "4. Check if the files are too large or complex"
            return error_msg, error_msg, [], None
        except Exception as e:
            # Restore stdout
            sys.stdout = old_stdout
            error_msg = f"Error during execution: {str(e)}\n{traceback.format_exc()}"
            return error_msg, error_msg, [], None
        finally:
            # Ensure stdout is restored
            if sys.stdout != old_stdout:
                sys.stdout = old_stdout
        
        # Check for newly generated files
        generated_files = []
        current_files = get_existing_output_files(output_folder)
        for file_path in current_files:
            if file_path not in existing_files:
                generated_files.append(file_path)
        
        # Try to read the summary file as the main answer
        main_answer = ""
        if os.path.exists(summary_filepath):
            try:
                with open(summary_filepath, "r", encoding="utf-8") as f:
                    main_answer = f.read().strip()
            except Exception as e:
                main_answer = f"Error reading summary file: {str(e)}"
        
        # If summary file doesn't exist or is empty, fall back to extracting from response
        if not main_answer:
            if not response_text.strip():
                response_text = "Code executed successfully. "
                if generated_files:
                    response_text += f"Generated {len(generated_files)} file(s)."
                else:
                    response_text += "No new files were generated."
            
            # Extract main answer from response text
            main_answer = extract_main_answer(response_text)
            
            # If we still don't have a good answer, provide a default message
            if not main_answer.strip() or len(main_answer.strip()) < 20:
                main_answer = "Analysis completed. Please check the generated files for results."
                if generated_files:
                    main_answer += f"\n\nGenerated files: {', '.join([os.path.basename(f) for f in generated_files])}"
        
        intermediate_steps = response_text  # Full response as intermediate steps
        
        # If summary file doesn't exist, create it automatically from the response
        if not os.path.exists(summary_filepath):
            # Try to extract a meaningful summary from the response
            summary_content = f"Analysis Summary\n{'='*80}\n\n"
            summary_content += f"Prompt: {prompt}\n\n"
            summary_content += f"Analysis Results:\n{'-'*80}\n\n"
            
            # Try to extract key findings from the response
            if response_text.strip():
                # Use the main answer as summary content
                summary_content += main_answer
            else:
                summary_content += "Analysis completed. Please check generated files for detailed results."
            
            # Add file information
            if generated_files:
                summary_content += f"\n\n{'='*80}\nGenerated Files:\n"
                for file_path in generated_files:
                    summary_content += f"- {os.path.basename(file_path)}\n"
            
            # Write the summary file
            try:
                with open(summary_filepath, "w", encoding="utf-8") as f:
                    f.write(summary_content)
                # Add to generated files if it wasn't already there
                if summary_filepath not in generated_files:
                    generated_files.append(summary_filepath)
            except Exception as e:
                # Log error but continue - summary creation is best effort
                print(f"Warning: Could not auto-create summary file: {str(e)}")
        
        # Save main answer to file (using summary file if it exists, otherwise create answer file)
        if os.path.exists(summary_filepath):
            answer_file_path = summary_filepath
        else:
            answer_file_path = save_answer_to_file(main_answer, prompt, output_folder)
        
        return main_answer, intermediate_steps, generated_files, answer_file_path
        
    except Exception as e:
        error_msg = f"Error using Open Interpreter: {str(e)}\n{traceback.format_exc()}"
        return error_msg, error_msg, [], None

# Main UI
st.title("📊 Analyze & Excel")
st.markdown("Upload or select files and analyze them with Open Interpreter")

# Sidebar for file selection
with st.sidebar:
    # Check if OpenAI is accessible (API key available)
    api_key = load_api_key()
    
    # Show configuration only if OpenAI is not accessible
    if not api_key:
        st.header("⚙️ Configuration")
        st.warning("⚠️ OpenAI API key not found")
        st.info("Please set OPENAI_API_KEY in your environment variables or .env file.")
        st.markdown("---")
    
    st.header("📁 File Selection")
    
    # Initialize modal state for file previews
    if 'view_file_modal' not in st.session_state:
        st.session_state.view_file_modal = None
    
    # Collect all selected files from folders and uploads
    all_selected_files = []
    for folder, folder_files in st.session_state.selected_folder_files.items():
        all_selected_files.extend(folder_files)
    all_selected_files.extend(st.session_state.uploaded_file_paths)
    
    # Count selected files for tab display
    selected_count = len(all_selected_files)
    
    # Create tabs for Folders, Upload, and Selected
    tab1, tab2, tab3 = st.tabs([f"📂 Folders", "⬆️ Upload", f"✅ Selected ({selected_count})"])
    
    with tab1:
        # Folders tab
        available_folders = get_available_folders()
        
        if available_folders:
            for folder in available_folders:
                # Get files in folder
                folder_files = load_files_from_folder(folder)
                file_count = len(folder_files)
                
                # Display folder name with Select button
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**📂 {folder}**")
                with col2:
                    if folder in st.session_state.selected_folder_files:
                        # Show Remove button if folder is already selected
                        if st.button("Remove", key=f"remove_{folder}", use_container_width=True):
                            del st.session_state.selected_folder_files[folder]
                            st.success(f"✅ {folder} removed from selections")
                            st.rerun()
                    else:
                        # Show Select button if folder is not selected
                        if st.button("Select", key=f"select_{folder}", use_container_width=True):
                            # Load all files from folder and add to selections
                            folder_files = load_files_from_folder(folder)
                            if folder_files:
                                st.session_state.selected_folder_files[folder] = folder_files
                                st.success(f"✅ {len(folder_files)} file(s) from {folder} added to selections")
                                st.rerun()
                            else:
                                st.warning(f"⚠️ No Excel or CSV files found in {folder}")
                
                # Show files in folder
                if folder_files:
                    for file_path in folder_files:
                        # Check if this file is selected (part of a selected folder)
                        is_selected = folder in st.session_state.selected_folder_files and file_path in st.session_state.selected_folder_files[folder]
                        
                        col1, col2 = st.columns([1, 20])
                        with col1:
                            # Show checkbox (read-only, just for visual indication)
                            st.checkbox("", value=is_selected, disabled=True, key=f"cb_{file_path}")
                        with col2:
                            st.text(f"📄 {os.path.basename(file_path)}")
                else:
                    st.info(f"No Excel or CSV files found in {folder}")
                st.markdown("---")
        else:
            st.info("No predefined folders found. You can create folders like 'input_folder_1', 'input_folder_2', etc.")
    
    with tab2:
        # Upload tab
        uploaded_files = st.file_uploader(
            "Upload Excel or CSV files",
            type=['xlsx', 'xls', 'csv'],
            accept_multiple_files=True,
            key="file_uploader"
        )
        
        # Process uploaded files and store in session state
        if uploaded_files:
            new_uploaded_paths = []
            for uploaded_file in uploaded_files:
                file_path = process_uploaded_file(uploaded_file)
                new_uploaded_paths.append(file_path)
                if file_path not in st.session_state.uploaded_file_paths:
                    st.session_state.uploaded_file_paths.append(file_path)
            
            st.success(f"✅ {len(uploaded_files)} file(s) uploaded and added to selections")
            st.markdown("---")
            for file_path in st.session_state.uploaded_file_paths:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {os.path.basename(file_path)}")
                with col2:
                    if st.button("👁️ View", key=f"view_upload_{file_path}", use_container_width=True):
                        st.session_state.view_file_modal = file_path
        else:
            if st.session_state.uploaded_file_paths:
                st.info(f"📋 {len(st.session_state.uploaded_file_paths)} previously uploaded file(s) in selections")
                for file_path in st.session_state.uploaded_file_paths:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.text(f"📄 {os.path.basename(file_path)}")
                    with col2:
                        if st.button("👁️ View", key=f"view_upload_{file_path}", use_container_width=True):
                            st.session_state.view_file_modal = file_path
            else:
                st.info("No files uploaded yet. Use the file uploader above to add files.")
    
    with tab3:
        # Selected files tab
        # Collect all files for display
        display_files = []
        for folder, folder_files in st.session_state.selected_folder_files.items():
            display_files.extend(folder_files)
        display_files.extend(st.session_state.uploaded_file_paths)
        
        if display_files:
            st.info(f"📊 Total: {len(display_files)} file(s) selected")
            for file_path in display_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Show which folder the file came from
                    file_folder = None
                    for folder, folder_files in st.session_state.selected_folder_files.items():
                        if file_path in folder_files:
                            file_folder = folder
                            break
                    if file_folder:
                        st.text(f"📄 {os.path.basename(file_path)} (from {file_folder})")
                    elif file_path in st.session_state.uploaded_file_paths:
                        st.text(f"📄 {os.path.basename(file_path)} (uploaded)")
                    else:
                        st.text(f"📄 {os.path.basename(file_path)}")
                with col2:
                    if st.button("👁️ View", key=f"view_{file_path}", use_container_width=True):
                        st.session_state.view_file_modal = file_path
        else:
            st.warning("No files selected. Please select folders or upload files.")
    
    # Final collection of all selected files (after tabs, to ensure uploaded files are included)
    # This ensures all_selected_files is up-to-date for the submit button
    all_selected_files = []
    for folder, folder_files in st.session_state.selected_folder_files.items():
        all_selected_files.extend(folder_files)
    
    # Add uploaded files from session state
    for file_path in st.session_state.uploaded_file_paths:
        if file_path not in all_selected_files:
            all_selected_files.append(file_path)
    
    # Show file preview modal if a file is selected
    if st.session_state.view_file_modal:
        # Use st.expander as fallback since st.dialog decorator pattern is complex
        with st.expander("📄 File Preview", expanded=True):
            show_file_preview_modal(st.session_state.view_file_modal)
            st.markdown("---")
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("❌ Close", use_container_width=True, type="secondary"):
                    st.session_state.view_file_modal = None
                    st.rerun()

# Main content area
st.header("💬 Enter Your Prompt")

# Prompt input
prompt = st.text_area(
    "Describe what you want to do with the files",
    height=150,
    placeholder="Example: Analyze the sales data and create a summary report with monthly totals..."
)

# Submit button
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    submit_button = st.button("🚀 Submit", type="primary", use_container_width=True)
with col2:
    clear_button = st.button("🗑️ Clear", use_container_width=True)

# Initialize modal state
if 'show_clear_modal' not in st.session_state:
    st.session_state.show_clear_modal = False

# Show modal when clear button is clicked
if clear_button:
    st.session_state.show_clear_modal = True

# Modal for clear confirmation
if st.session_state.show_clear_modal:
    # Use st.expander as fallback since st.dialog decorator pattern is complex
    with st.expander("⚠️ Confirm Clear", expanded=True):
        st.markdown("**Are you sure you want to clear all data?**")
        st.markdown("This will remove all messages, files, and processed dataframes.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Clear", type="primary", use_container_width=True):
                st.session_state.messages = []
                st.session_state.output_files = []
                st.session_state.processed_dataframes = {}
                st.session_state.selected_sheets = {}
                st.session_state.selected_folder_files = {}
                st.session_state.uploaded_file_paths = []
                st.session_state.show_clear_modal = False
                st.rerun()
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_clear_modal = False
                st.rerun()

# Process submission
if submit_button:
    if not all_selected_files:
        st.error("Please select files or upload files first!")
    elif not prompt.strip():
        st.error("Please enter a prompt!")
    else:
        # Show loading spinner while processing
        status_container = st.empty()
        with status_container.container():
            st.info("🔄 Processing your request with Open Interpreter... Please wait.")
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        try:
            # Get timeout from environment or use default (5 minutes)
            timeout_seconds = load_timeout()
            
            # Call Open Interpreter with timeout
            main_answer, intermediate_steps, generated_files, answer_file_path = call_openai_code_interpreter(
                prompt, 
                all_selected_files, 
                OUTPUT_FOLDER,
                timeout_seconds=timeout_seconds
            )
            
            # Clear loading indicators
            status_container.empty()
            progress_bar.empty()
            status_text.empty()
            
            # Store response
            st.session_state.messages.append({
                "prompt": prompt,
                "main_answer": main_answer,
                "intermediate_steps": intermediate_steps,
                "files": generated_files,
                "answer_file": answer_file_path
            })
            
            # Update output files (include answer file)
            all_output_files = generated_files.copy()
            if answer_file_path:
                all_output_files.append(answer_file_path)
            st.session_state.output_files = all_output_files
            
            # Load generated dataframes (skip text files)
            for file_path in generated_files:
                if file_path not in st.session_state.processed_dataframes:
                    # Only load Excel/CSV files, not text files
                    if not file_path.endswith('.txt'):
                        data = read_excel_or_csv(file_path)
                        if isinstance(data, dict):
                            # Excel file with multiple sheets
                            st.session_state.processed_dataframes[file_path] = data
                            # Set default selected sheet to first sheet
                            if file_path not in st.session_state.selected_sheets:
                                st.session_state.selected_sheets[file_path] = list(data.keys())[0] if data else None
                        elif isinstance(data, pd.DataFrame) and not data.empty:
                            # CSV or single sheet Excel
                            st.session_state.processed_dataframes[file_path] = data
            
            # Mark that we should show summary tab if summary exists
            if answer_file_path and os.path.basename(answer_file_path).startswith('summary_'):
                st.session_state.active_tab_index[len(st.session_state.messages) - 1] = 0  # Summary tab
            
            # Success message - the results will be displayed below automatically
            if generated_files:
                st.success(f"✅ Successfully generated {len(generated_files)} file(s)!")
        except TimeoutError as e:
            status_container.empty()
            progress_bar.empty()
            status_text.empty()
            st.error(f"⏱️ Timeout Error: {str(e)}")
            st.warning("💡 Tip: Try simplifying your request, reducing file sizes, or increasing the TIMEOUT_SECONDS in your environment/.env file.")
        except Exception as e:
            status_container.empty()
            progress_bar.empty()
            status_text.empty()
            error_msg = str(e)
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                st.error(f"⏱️ Timeout Error: {error_msg}")
                st.warning("💡 Tip: Try simplifying your request, reducing file sizes, or increasing the TIMEOUT_SECONDS in your environment/.env file.")
            else:
                st.error(f"Error during processing: {error_msg}")
                st.exception(e)

# Display conversation history
if st.session_state.messages:
    st.header("📝 Generated Responses")
    
    reversed_messages = list(reversed(st.session_state.messages[-5:]))  # Show last 5 responses
    
    for i, msg in enumerate(reversed_messages):
        # Get message data (handle both old and new format)
        prompt_text = msg.get('prompt', '')
        main_answer = msg.get('main_answer', msg.get('response', ''))
        intermediate_steps = msg.get('intermediate_steps', '')
        generated_files = msg.get('files', [])
        answer_file = msg.get('answer_file', None)
        
        # Combine all output files (generated files + answer file)
        all_output_files = generated_files.copy()
        if answer_file and answer_file not in all_output_files:
            all_output_files.append(answer_file)
        
        # Check if summary file exists and should be shown first
        has_summary = answer_file and os.path.basename(answer_file).startswith('summary_')
        
        # For the most recent answer (i == 0), show it normally
        # For previous answers (i > 0), show them in collapsible expanders
        if i > 0:
            # Previous answers - show in collapsible expander
            # Truncate prompt for display if too long
            display_prompt = prompt_text[:60] + "..." if len(prompt_text) > 60 else prompt_text
            with st.expander(f"📜 Previous Answer: {display_prompt}", expanded=False):
                st.markdown(f"**Prompt:** {prompt_text}")
                st.markdown("---")
                
                # Create tabs - put Summary first if available, otherwise Main Answer
                if has_summary:
                    tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔍 Intermediate Steps", "📊 Generated Files"])
                else:
                    tab1, tab2, tab3 = st.tabs(["✨ Main Answer", "🔍 Intermediate Steps", "📊 Generated Files"])
                
                with tab1:
                    # Display main answer
                    st.markdown(main_answer)
                    
                    # Show answer file info and download
                    if answer_file and os.path.exists(answer_file):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.success(f"✅ Answer saved to: `{os.path.basename(answer_file)}`")
                        with col2:
                            with open(answer_file, "rb") as f:
                                st.download_button(
                                    label="📥 Download Answer",
                                    data=f.read(),
                                    file_name=os.path.basename(answer_file),
                                    mime="text/plain",
                                    key=f"download_answer_{i}"
                                )
                
                with tab2:
                    # Display intermediate steps in scrolled window
                    if intermediate_steps and intermediate_steps != main_answer:
                        st.markdown("**Execution Details:**")
                        st.text_area(
                            "Intermediate steps and execution logs",
                            value=intermediate_steps,
                            height=500,
                            key=f"intermediate_{i}",
                            label_visibility="collapsed",
                            disabled=True  # Make it read-only and scrollable
                        )
                    else:
                        st.info("No intermediate steps available.")
                
                with tab3:
                    # Generated Files tab with file viewer
                    if all_output_files:
                        # Create file name tabs at the top
                        file_tabs = st.tabs([os.path.basename(f) for f in all_output_files])
                        
                        for tab_idx, file_path in enumerate(all_output_files):
                            with file_tabs[tab_idx]:
                                if os.path.exists(file_path):
                                    # Check if it's a text file (answer file)
                                    if file_path.endswith('.txt'):
                                        # Display text file content
                                        with open(file_path, "r", encoding="utf-8") as f:
                                            file_content = f.read()
                                        
                                        st.markdown("**File Content:**")
                                        st.text_area(
                                            "File content",
                                            value=file_content,
                                            height=400,
                                            key=f"text_viewer_{file_path}_{i}",
                                            label_visibility="collapsed"
                                        )
                                        
                                        # Download button for text file
                                        with open(file_path, "rb") as f:
                                            st.download_button(
                                                label="📥 Download Text File",
                                                data=f.read(),
                                                file_name=os.path.basename(file_path),
                                                mime="text/plain",
                                                key=f"download_text_{file_path}_{i}"
                                            )
                                    
                                    # Check if it's a dataframe file
                                    elif file_path in st.session_state.processed_dataframes:
                                        # Get sheet names for this file
                                        sheet_names = get_sheet_names(file_path)
                                        
                                        # Show sheet selection buttons if multiple sheets
                                        if sheet_names and len(sheet_names) > 1:
                                            st.markdown("**Select Sheet:**")
                                            # Create buttons for each sheet
                                            cols = st.columns(min(len(sheet_names), 5))  # Max 5 columns
                                            for idx, sheet_name in enumerate(sheet_names):
                                                with cols[idx % len(cols)]:
                                                    button_key = f"sheet_btn_{file_path}_{sheet_name}_{i}"
                                                    is_selected = st.session_state.selected_sheets.get(file_path) == sheet_name
                                                    if st.button(
                                                        sheet_name,
                                                        key=button_key,
                                                        type="primary" if is_selected else "secondary",
                                                        use_container_width=True
                                                    ):
                                                        st.session_state.selected_sheets[file_path] = sheet_name
                                                        st.rerun()
                                        
                                        # Get current dataframe (handles multi-sheet)
                                        df = get_current_dataframe(file_path)
                                        
                                        if df is not None and not df.empty:
                                            # Show current sheet name if multi-sheet
                                            if sheet_names and len(sheet_names) > 1:
                                                current_sheet = st.session_state.selected_sheets.get(file_path, sheet_names[0])
                                                st.markdown(f"**Current Sheet: {current_sheet}**")
                                            
                                            # File info
                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                st.metric("Rows", len(df))
                                            with col2:
                                                st.metric("Columns", len(df.columns))
                                            with col3:
                                                st.metric("File Size", f"{os.path.getsize(file_path) / 1024:.2f} KB")
                                            
                                            # DataFrame display
                                            st.dataframe(df, use_container_width=True)
                                            
                                            # Download button
                                            if file_path.endswith('.csv'):
                                                csv = df.to_csv(index=False).encode('utf-8')
                                                st.download_button(
                                                    label="📥 Download CSV",
                                                    data=csv,
                                                    file_name=os.path.basename(file_path),
                                                    mime="text/csv",
                                                    key=f"download_csv_{file_path}_{i}"
                                                )
                                            else:
                                                # For Excel, we'll use the existing file
                                                with open(file_path, "rb") as f:
                                                    st.download_button(
                                                        label="📥 Download Excel",
                                                        data=f.read(),
                                                        file_name=os.path.basename(file_path),
                                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                        key=f"download_excel_{file_path}_{i}"
                                                    )
                                        else:
                                            st.warning("No data available to display.")
                                    else:
                                        # Try to read as dataframe if not in cache (skip text files)
                                        if not file_path.endswith('.txt'):
                                            try:
                                                data = read_excel_or_csv(file_path)
                                                if isinstance(data, dict):
                                                    # Excel file with multiple sheets
                                                    st.session_state.processed_dataframes[file_path] = data
                                                    # Set default selected sheet to first sheet
                                                    if file_path not in st.session_state.selected_sheets:
                                                        st.session_state.selected_sheets[file_path] = list(data.keys())[0] if data else None
                                                    st.rerun()
                                                elif isinstance(data, pd.DataFrame) and not data.empty:
                                                    st.session_state.processed_dataframes[file_path] = data
                                                    st.rerun()
                                                else:
                                                    st.warning("Could not read file as dataframe.")
                                            except:
                                                st.warning("File type not supported for preview. You can still download it.")
                                                with open(file_path, "rb") as f:
                                                    st.download_button(
                                                        label="📥 Download File",
                                                        data=f.read(),
                                                        file_name=os.path.basename(file_path),
                                                        mime="application/octet-stream",
                                                        key=f"download_file_{file_path}_{i}"
                                                    )
                                        else:
                                            st.warning("Text files are displayed in the text viewer above.")
                                else:
                                    st.warning(f"File not found: {os.path.basename(file_path)}")
                    else:
                        st.info("No generated files available.")
        else:
            # Most recent answer - show normally (not collapsed)
            st.subheader("✨ Current Answer")
            st.markdown(f"**Prompt:** {prompt_text}")
            st.markdown("---")
            
            # Create tabs - put Summary first if available, otherwise Main Answer
            if has_summary:
                tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔍 Intermediate Steps", "📊 Generated Files"])
            else:
                tab1, tab2, tab3 = st.tabs(["✨ Main Answer", "🔍 Intermediate Steps", "📊 Generated Files"])
            
            with tab1:
                # Display main answer
                st.markdown(main_answer)
                
                # Show answer file info and download
                if answer_file and os.path.exists(answer_file):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.success(f"✅ Answer saved to: `{os.path.basename(answer_file)}`")
                    with col2:
                        with open(answer_file, "rb") as f:
                            st.download_button(
                                label="📥 Download Answer",
                                data=f.read(),
                                file_name=os.path.basename(answer_file),
                                mime="text/plain",
                                key=f"download_answer_{i}"
                            )
            
            with tab2:
                # Display intermediate steps in scrolled window
                if intermediate_steps and intermediate_steps != main_answer:
                    st.markdown("**Execution Details:**")
                    st.text_area(
                        "Intermediate steps and execution logs",
                        value=intermediate_steps,
                        height=500,
                        key=f"intermediate_{i}",
                        label_visibility="collapsed",
                        disabled=True  # Make it read-only and scrollable
                    )
                else:
                    st.info("No intermediate steps available.")
            
            with tab3:
                # Generated Files tab with file viewer
                if all_output_files:
                    # Create file name tabs at the top
                    file_tabs = st.tabs([os.path.basename(f) for f in all_output_files])
                    
                    for tab_idx, file_path in enumerate(all_output_files):
                        with file_tabs[tab_idx]:
                            if os.path.exists(file_path):
                                # Check if it's a text file (answer file)
                                if file_path.endswith('.txt'):
                                    # Display text file content
                                    with open(file_path, "r", encoding="utf-8") as f:
                                        file_content = f.read()
                                    
                                    st.markdown("**File Content:**")
                                    st.text_area(
                                        "File content",
                                        value=file_content,
                                        height=400,
                                        key=f"text_viewer_{file_path}_{i}",
                                        label_visibility="collapsed"
                                    )
                                    
                                    # Download button for text file
                                    with open(file_path, "rb") as f:
                                        st.download_button(
                                            label="📥 Download Text File",
                                            data=f.read(),
                                            file_name=os.path.basename(file_path),
                                            mime="text/plain",
                                            key=f"download_text_{file_path}_{i}"
                                        )
                                
                                # Check if it's a dataframe file
                                elif file_path in st.session_state.processed_dataframes:
                                    # Get sheet names for this file
                                    sheet_names = get_sheet_names(file_path)
                                    
                                    # Show sheet selection buttons if multiple sheets
                                    if sheet_names and len(sheet_names) > 1:
                                        st.markdown("**Select Sheet:**")
                                        # Create buttons for each sheet
                                        cols = st.columns(min(len(sheet_names), 5))  # Max 5 columns
                                        for idx, sheet_name in enumerate(sheet_names):
                                            with cols[idx % len(cols)]:
                                                button_key = f"sheet_btn_{file_path}_{sheet_name}_{i}"
                                                is_selected = st.session_state.selected_sheets.get(file_path) == sheet_name
                                                if st.button(
                                                    sheet_name,
                                                    key=button_key,
                                                    type="primary" if is_selected else "secondary",
                                                    use_container_width=True
                                                ):
                                                    st.session_state.selected_sheets[file_path] = sheet_name
                                                    st.rerun()
                                    
                                    # Get current dataframe (handles multi-sheet)
                                    df = get_current_dataframe(file_path)
                                    
                                    if df is not None and not df.empty:
                                        # Show current sheet name if multi-sheet
                                        if sheet_names and len(sheet_names) > 1:
                                            current_sheet = st.session_state.selected_sheets.get(file_path, sheet_names[0])
                                            st.markdown(f"**Current Sheet: {current_sheet}**")
                                        
                                        # File info
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("Rows", len(df))
                                        with col2:
                                            st.metric("Columns", len(df.columns))
                                        with col3:
                                            st.metric("File Size", f"{os.path.getsize(file_path) / 1024:.2f} KB")
                                        
                                        # DataFrame display
                                        st.dataframe(df, use_container_width=True)
                                        
                                        # Download button
                                        if file_path.endswith('.csv'):
                                            csv = df.to_csv(index=False).encode('utf-8')
                                            st.download_button(
                                                label="📥 Download CSV",
                                                data=csv,
                                                file_name=os.path.basename(file_path),
                                                mime="text/csv",
                                                key=f"download_csv_{file_path}_{i}"
                                            )
                                        else:
                                            # For Excel, we'll use the existing file
                                            with open(file_path, "rb") as f:
                                                st.download_button(
                                                    label="📥 Download Excel",
                                                    data=f.read(),
                                                    file_name=os.path.basename(file_path),
                                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                    key=f"download_excel_{file_path}_{i}"
                                                )
                                    else:
                                        st.warning("No data available to display.")
                                else:
                                    # Try to read as dataframe if not in cache (skip text files)
                                    if not file_path.endswith('.txt'):
                                        try:
                                            data = read_excel_or_csv(file_path)
                                            if isinstance(data, dict):
                                                # Excel file with multiple sheets
                                                st.session_state.processed_dataframes[file_path] = data
                                                # Set default selected sheet to first sheet
                                                if file_path not in st.session_state.selected_sheets:
                                                    st.session_state.selected_sheets[file_path] = list(data.keys())[0] if data else None
                                                st.rerun()
                                            elif isinstance(data, pd.DataFrame) and not data.empty:
                                                st.session_state.processed_dataframes[file_path] = data
                                                st.rerun()
                                            else:
                                                st.warning("Could not read file as dataframe.")
                                        except:
                                            st.warning("File type not supported for preview. You can still download it.")
                                            with open(file_path, "rb") as f:
                                                st.download_button(
                                                    label="📥 Download File",
                                                    data=f.read(),
                                                    file_name=os.path.basename(file_path),
                                                    mime="application/octet-stream",
                                                    key=f"download_file_{file_path}_{i}"
                                                )
                                    else:
                                        st.warning("Text files are displayed in the text viewer above.")
                            else:
                                st.warning(f"File not found: {os.path.basename(file_path)}")
                else:
                    st.info("No generated files available.")
        
        # Add separator only if not the last message
        if i < len(reversed_messages) - 1:
            st.markdown("---")

# Footer

