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

# Constants
INPUT_FOLDERS = ["input_folder_1", "input_folder_2", "input_folder_3"]  # Predefined folder names
OUTPUT_FOLDER = "output"
UPLOAD_FOLDER = "uploads"

# Create necessary directories
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load OpenAI API key
def load_api_key():
    """Load API key from environment, .env file, or session state"""
    from dotenv import load_dotenv
    load_dotenv()
    
    # First check environment variable
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    
    # Then check session state (from UI input)
    if 'openai_api_key' in st.session_state and st.session_state.openai_api_key:
        return st.session_state.openai_api_key
    
    return None

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

def read_excel_or_csv(file_path: str) -> pd.DataFrame:
    """Read Excel or CSV file into DataFrame"""
    try:
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        else:
            return pd.read_excel(file_path)
    except Exception as e:
        st.error(f"Error reading {file_path}: {str(e)}")
        return pd.DataFrame()

def get_file_context(file_paths: List[str]) -> str:
    """Create context string from file paths for the prompt"""
    context = "Available files:\n"
    for file_path in file_paths:
        try:
            df = read_excel_or_csv(file_path)
            context += f"\n- {os.path.basename(file_path)}: {len(df)} rows, {len(df.columns)} columns\n"
            context += f"  Columns: {', '.join(df.columns.tolist())}\n"
        except Exception as e:
            context += f"\n- {os.path.basename(file_path)}: Error reading file\n"
    return context

def get_existing_output_files(output_folder: str) -> set:
    """Get set of existing output files before execution"""
    existing_files = set()
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            if file.endswith(('.xlsx', '.xls', '.csv')):
                existing_files.add(os.path.join(output_folder, file))
    return existing_files

def call_openai_code_interpreter(prompt: str, file_paths: List[str], output_folder: str) -> tuple:
    """
    Call Open Interpreter to analyze files and execute code
    Returns: (response_text, generated_files)
    """
    api_key = load_api_key()
    if not api_key:
        return "Error: OpenAI API key not found. Please enter your API key in the sidebar (Configuration section) or set OPENAI_API_KEY in your environment/.env file.", []
    
    # Get existing files before execution
    existing_files = get_existing_output_files(output_folder)
    
    # Configure Open Interpreter
    interpreter.api_key = api_key
    interpreter.auto_run = True  # Automatically execute code
    interpreter.verbose = False   # Reduce output for Streamlit
    
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
6. Provide clear explanations of what you're doing"""
    
    try:
        # Create the full prompt with context
        full_prompt = f"{system_context}\n\nUser request: {prompt}"
        
        # Capture stdout to get Open Interpreter's output
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        
        try:
            sys.stdout = output_buffer
            
            # Use Open Interpreter to chat and execute code
            # Open Interpreter will execute code and print output
            interpreter.chat(full_prompt)
            
            # Get the captured output
            response_text = output_buffer.getvalue()
            
        finally:
            sys.stdout = old_stdout
        
        # Check for newly generated files
        generated_files = []
        current_files = get_existing_output_files(output_folder)
        for file_path in current_files:
            if file_path not in existing_files:
                generated_files.append(file_path)
        
        # If no response text was captured, provide a summary
        if not response_text.strip():
            response_text = "Code executed successfully. "
            if generated_files:
                response_text += f"Generated {len(generated_files)} file(s)."
            else:
                response_text += "No new files were generated."
        
        return response_text, generated_files
        
    except Exception as e:
        error_msg = f"Error using Open Interpreter: {str(e)}\n{traceback.format_exc()}"
        return error_msg, []

# Main UI
st.title("📊 Analyze & Excel")
st.markdown("Upload or select files and analyze them with Open Interpreter")

# Sidebar for file selection
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key input
    api_key_from_env = os.getenv("OPENAI_API_KEY")
    if not api_key_from_env:
        st.subheader("🔑 OpenAI API Key")
        api_key_input = st.text_input(
            "Enter your OpenAI API Key",
            type="password",
            value=st.session_state.get('openai_api_key', ''),
            help="You can also set OPENAI_API_KEY in a .env file or environment variable",
            key="api_key_input"
        )
        if api_key_input:
            st.session_state.openai_api_key = api_key_input
            st.success("✅ API Key saved (session only)")
        else:
            st.warning("⚠️ API Key required to use the app")
    else:
        st.success("✅ API Key loaded from environment")
    
    st.markdown("---")
    
    st.header("📁 File Selection")
    
    # Option 1: Select predefined folders
    st.subheader("Select Predefined Folders")
    available_folders = get_available_folders()
    
    selected_folders = []
    if available_folders:
        for folder in available_folders:
            if st.checkbox(f"📂 {folder}", key=f"folder_{folder}"):
                selected_folders.append(folder)
    else:
        st.info("No predefined folders found. You can create folders like 'input_folder_1', 'input_folder_2', etc.")
    
    # Option 2: Upload files
    st.subheader("Upload Files")
    uploaded_files = st.file_uploader(
        "Upload Excel or CSV files",
        type=['xlsx', 'xls', 'csv'],
        accept_multiple_files=True,
        key="file_uploader"
    )
    
    # Display selected files
    st.subheader("Selected Files")
    all_selected_files = []
    
    # Add files from folders
    for folder in selected_folders:
        folder_files = load_files_from_folder(folder)
        all_selected_files.extend(folder_files)
        for file_path in folder_files:
            st.text(f"📄 {os.path.basename(file_path)}")
    
    # Add uploaded files
    uploaded_file_paths = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_path = process_uploaded_file(uploaded_file)
            uploaded_file_paths.append(file_path)
            all_selected_files.append(file_path)
            st.text(f"📄 {uploaded_file.name}")
    
    if not all_selected_files:
        st.warning("No files selected. Please select folders or upload files.")

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

if clear_button:
    st.session_state.messages = []
    st.session_state.output_files = []
    st.session_state.processed_dataframes = {}
    st.rerun()

# Process submission
if submit_button:
    if not all_selected_files:
        st.error("Please select files or upload files first!")
    elif not prompt.strip():
        st.error("Please enter a prompt!")
    else:
        with st.spinner("Processing your request with Open Interpreter..."):
            # Call Open Interpreter
            response_text, generated_files = call_openai_code_interpreter(
                prompt, 
                all_selected_files, 
                OUTPUT_FOLDER
            )
            
            # Store response
            st.session_state.messages.append({
                "prompt": prompt,
                "response": response_text,
                "files": generated_files
            })
            
            # Update output files
            st.session_state.output_files = generated_files
            
            # Load generated dataframes
            for file_path in generated_files:
                if file_path not in st.session_state.processed_dataframes:
                    df = read_excel_or_csv(file_path)
                    st.session_state.processed_dataframes[file_path] = df

# Display conversation history
if st.session_state.messages:
    st.header("📝 Generated Responses")
    
    for i, msg in enumerate(reversed(st.session_state.messages[-5:])):  # Show last 5 responses
        with st.expander(f"💬 Prompt: {msg['prompt'][:50]}...", expanded=(i == 0)):
            st.markdown("**Your Prompt:**")
            st.write(msg['prompt'])
            
            st.markdown("**AI Response:**")
            st.write(msg['response'])
            
            if msg['files']:
                st.markdown("**Generated Files:**")
                for file_path in msg['files']:
                    st.text(f"📊 {os.path.basename(file_path)}")

# Display dataframe viewer
if st.session_state.output_files:
    st.header("📊 Generated Excel Files Viewer")
    
    # File selector
    selected_file = st.selectbox(
        "Select a file to view",
        options=st.session_state.output_files,
        format_func=lambda x: os.path.basename(x)
    )
    
    if selected_file and selected_file in st.session_state.processed_dataframes:
        df = st.session_state.processed_dataframes[selected_file]
        
        st.subheader(f"📄 {os.path.basename(selected_file)}")
        
        # File info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rows", len(df))
        with col2:
            st.metric("Columns", len(df.columns))
        with col3:
            st.metric("File Size", f"{os.path.getsize(selected_file) / 1024:.2f} KB")
        
        # DataFrame display
        st.dataframe(df, use_container_width=True)
        
        # Download button
        if selected_file.endswith('.csv'):
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=os.path.basename(selected_file),
                mime="text/csv"
            )
        else:
            # For Excel, we'll use the existing file
            with open(selected_file, "rb") as f:
                st.download_button(
                    label="📥 Download Excel",
                    data=f.read(),
                    file_name=os.path.basename(selected_file),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# Footer
st.markdown("---")
st.markdown("**Note:** Make sure to set your OPENAI_API_KEY in a `.env` file or environment variables.")

