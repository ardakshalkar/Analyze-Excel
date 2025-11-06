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

## Usage

1. Start the Streamlit app:
```bash
streamlit run app.py
```

2. In the sidebar:
   - Select predefined folders (create folders like `input_folder_1`, `input_folder_2`, etc. if needed)
   - OR upload Excel/CSV files directly

3. Enter your prompt in the text area describing what you want to do with the files

4. Click "Submit" to process your request

5. View the generated response and explore resulting Excel files in the DataFrame viewer

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

