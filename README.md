# Analyze & Excel - Streamlit Application

A Streamlit application that allows users to analyze Excel and CSV files using AI-powered code interpreter.

## Features

- **File Selection**: Select from predefined folders or upload files directly
- **Support for Excel and CSV**: Works with `.xlsx`, `.xls`, and `.csv` files
- **AI-Powered Analysis**: Enter prompts to analyze data using OpenAI's code interpreter
- **Output Management**: Generated Excel files are saved to an output folder
- **DataFrame Viewer**: View and explore generated Excel files directly in the app
- **Response History**: View previous prompts and responses

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your OpenAI API key:
   - Create a `.env` file in the root directory
   - Add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_api_key_here
   ```
   - Alternatively, you can set the environment variable directly:
   ```bash
   # Windows
   set OPENAI_API_KEY=your_actual_api_key_here
   
   # Linux/Mac
   export OPENAI_API_KEY=your_actual_api_key_here
   ```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up API Key
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_actual_api_key_here
```

### 3. Run the App

**Windows users can simply double-click `run_app.bat`**

Or run manually:
```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`

**Alternative if `streamlit` command doesn't work:**
```bash
python -m streamlit run app.py
```

## Usage

1. **Select Files:**
   - In the sidebar, select predefined folders (create folders like `input_folder_1`, `input_folder_2`, etc. if needed)
   - OR upload Excel/CSV files directly using the file uploader

2. **Enter Your Prompt:**
   - Type what you want to analyze in the text area
   - Example: "Analyze sales data and create a monthly summary"

3. **Submit:**
   - Click "🚀 Submit" to process your request
   - Wait for the analysis to complete (may take a few minutes)

4. **View Results:**
   - See the generated response in the main area
   - Download generated Excel files
   - Explore resulting dataframes in the interactive viewer

## Folder Structure

```
Analyze&Excel/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── input_folder_1/       # Predefined input folder (optional)
├── input_folder_2/       # Predefined input folder (optional)
├── uploads/              # Uploaded files storage (auto-created)
└── output/               # Generated Excel files (auto-created)
```

## Notes

- The app automatically creates `uploads/` and `output/` folders
- Generated files are saved in the `output/` folder
- You can create predefined input folders manually or let users upload files
- Make sure you have a valid OpenAI API key with access to GPT-4 or GPT-3.5-turbo

## Timeout Configuration

The app includes a timeout mechanism to prevent requests from running indefinitely. By default, requests timeout after 5 minutes (300 seconds).

### Adjusting Timeout

1. **Via UI**: Use the "Timeout Settings" in the sidebar to adjust the timeout (1-60 minutes)
2. **For Complex Operations**: Increase the timeout if you're working with large files or complex analysis

### Troubleshooting Timeout Issues

If you encounter timeout errors:

1. **Increase Timeout**: Use the sidebar timeout settings to increase the limit
2. **Simplify Requests**: Break complex requests into smaller, simpler tasks
3. **Reduce File Size**: Work with smaller datasets or sample data first
4. **Check File Complexity**: Very large or complex Excel files may require more time

### Streamlit Server Timeout

If you're running Streamlit in production, you may also need to configure the server timeout:

```bash
# Run with increased timeout (10 minutes)
streamlit run app.py --server.runOnSave=false --server.headless=true
```

Or create a `.streamlit/config.toml` file:
```toml
[server]
runOnSave = false
headless = true
```

## Example Prompts

- "Create a summary report with total sales by month"
- "Analyze the data and identify top 10 customers"
- "Calculate average values for each category"
- "Merge the two Excel files and create a new combined report"

## Troubleshooting

### Problem: "streamlit: command not found"
**Solution:** Use `python -m streamlit run app.py` instead

### Problem: "AttributeError: module 'streamlit' has no attribute 'dialog'"
**Solution:** Upgrade Streamlit to version 1.29.0 or higher:
```bash
python -m pip install --upgrade streamlit>=1.29.0
```

### Problem: "ModuleNotFoundError: No module named 'xxx'"
**Solution:** Install missing packages:
```bash
python -m pip install -r requirements.txt
```

### Problem: NumPy Compatibility Error (`AttributeError: module 'numpy' has no attribute 'bool8'`)
**Solution:** Downgrade NumPy to a compatible version:
```bash
python -m pip install "numpy>=1.24.0,<2.0.0" --force-reinstall
```

### Problem: Commands work in IDE but not in terminal
**Solution:** 
- Use **Anaconda Prompt** instead of regular Command Prompt (if you have Anaconda)
- Or check which Python your terminal is using:
  ```bash
  python -c "import sys; print(sys.executable)"
  ```
- Make sure it matches the Python that has the packages installed

### Problem: Port 8501 already in use
**Solution:** Use a different port:
```bash
streamlit run app.py --server.port 8502
```

## Deployment

### Streamlit Cloud Deployment

⚠️ **IMPORTANT:** Set Python version to **3.12** (or 3.11) in Streamlit Cloud settings before deploying!

1. Push your code to GitHub (make sure repository is public or you have Pro)
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click "New app" → Select repository and branch → Set main file: `app.py`
4. **In Settings, change Python version to 3.12** (to avoid tiktoken build errors)
5. Set secrets (API Key) in app settings:
   ```toml
   OPENAI_API_KEY = "your_api_key_here"
   ```
6. Click "Deploy"

**Note:** `runtime.txt` should specify Python 3.12 for best compatibility.

