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
if 'active_tab_index' not in st.session_state:
    st.session_state.active_tab_index = {}

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
    # Skip text files
    if file_path.endswith('.txt'):
        return pd.DataFrame()
    
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
            # Skip text files in context (they're output files, not input files)
            if file_path.endswith('.txt'):
                context += f"\n- {os.path.basename(file_path)}: Text file\n"
                continue
            
            df = read_excel_or_csv(file_path)
            if not df.empty:
                context += f"\n- {os.path.basename(file_path)}: {len(df)} rows, {len(df.columns)} columns\n"
                context += f"  Columns: {', '.join(df.columns.tolist())}\n"
            else:
                context += f"\n- {os.path.basename(file_path)}: Empty or unsupported file\n"
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

def call_openai_code_interpreter(prompt: str, file_paths: List[str], output_folder: str) -> tuple:
    """
    Call Open Interpreter to analyze files and execute code
    Returns: (main_answer, intermediate_steps, generated_files, answer_file_path)
    """
    api_key = load_api_key()
    if not api_key:
        error_msg = "Error: OpenAI API key not found. Please enter your API key in the sidebar (Configuration section) or set OPENAI_API_KEY in your environment/.env file."
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
        # Show loading spinner while processing
        status_container = st.empty()
        with status_container.container():
            st.info("🔄 Processing your request with Open Interpreter... Please wait.")
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        try:
            # Call Open Interpreter
            main_answer, intermediate_steps, generated_files, answer_file_path = call_openai_code_interpreter(
                prompt, 
                all_selected_files, 
                OUTPUT_FOLDER
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
                        df = read_excel_or_csv(file_path)
                        if not df.empty:
                            st.session_state.processed_dataframes[file_path] = df
            
            # Mark that we should show summary tab if summary exists
            if answer_file_path and os.path.basename(answer_file_path).startswith('summary_'):
                st.session_state.active_tab_index[len(st.session_state.messages) - 1] = 0  # Summary tab
        except Exception as e:
            status_container.empty()
            progress_bar.empty()
            status_text.empty()
            st.error(f"Error during processing: {str(e)}")

# Display conversation history
if st.session_state.messages:
    st.header("📝 Generated Responses")
    
    for i, msg in enumerate(reversed(st.session_state.messages[-5:])):  # Show last 5 responses
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
                                df = st.session_state.processed_dataframes[file_path]
                                
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
                                # Try to read as dataframe if not in cache (skip text files)
                                if not file_path.endswith('.txt'):
                                    try:
                                        df = read_excel_or_csv(file_path)
                                        if not df.empty:
                                            st.session_state.processed_dataframes[file_path] = df
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
        
        st.markdown("---")

# Footer
st.markdown("---")
st.markdown("**Note:** Make sure to set your OPENAI_API_KEY in a `.env` file or environment variables.")

