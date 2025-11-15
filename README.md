# Analyze & Excel - Multi-Platform Application

A comprehensive data analysis application with three interfaces:
- **Streamlit App**: Original web interface for data analysis
- **FastAPI Backend**: RESTful API for programmatic access
- **Vue.js Frontend**: Modern web interface built with Vue 3

## Features

- **File Selection**: Select from predefined folders or upload files directly
- **Support for Excel and CSV**: Works with `.xlsx`, `.xls`, and `.csv` files
- **AI-Powered Analysis**: Enter prompts to analyze data using OpenAI's code interpreter
- **Output Management**: Generated Excel files are saved to an output folder
- **Multiple Interfaces**: Choose between Streamlit, Vue.js frontend, or API access
- **Real-time Progress**: Track analysis progress in real-time (Vue.js frontend)

## Project Structure

```
Analyze&Excel/
├── app.py                 # Streamlit application
├── api/
│   └── main.py           # FastAPI backend
├── frontend/             # Vue.js frontend
│   ├── src/
│   │   ├── App.vue       # Main Vue component
│   │   ├── main.js       # Vue entry point
│   │   └── style.css     # Styles
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── requirements.txt      # Python dependencies
├── run_app.bat          # Run Streamlit app
├── run_api.bat          # Run FastAPI server
└── run_frontend.bat     # Run Vue.js frontend
```

## Installation

### 1. Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Node.js Dependencies (for Vue.js frontend)

```bash
cd frontend
npm install
```

### 3. Environment Setup

Create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_actual_api_key_here
```

## Running the Applications

### Option 1: Streamlit App (Original)

**Windows:**
```bash
run_app.bat
```

**Manual:**
```bash
streamlit run app.py
```

Access at: `http://localhost:8501`

### Option 2: FastAPI Backend + Vue.js Frontend

**Step 1: Start FastAPI Backend**

**Windows:**
```bash
run_api.bat
```

**Manual:**
```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

**Step 2: Start Vue.js Frontend**

**Windows:**
```bash
run_frontend.bat
```

**Manual:**
```bash
cd frontend
npm run dev
```

Frontend will be available at: `http://localhost:5173`

### Option 3: FastAPI Backend Only (API Access)

Start the FastAPI server and use the REST API directly:

```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health & Info
- `GET /` - API information
- `GET /health` - Health check

### Files
- `GET /api/folders` - Get available input folders
- `GET /api/files` - List all available files
- `POST /api/upload` - Upload a file
- `GET /api/files/{file_path}/preview` - Preview file data
- `GET /api/download/{file_path}` - Download a file

### Analysis
- `POST /api/analyze` - Start analysis task
  ```json
  {
    "prompt": "Analyze the data...",
    "file_paths": ["path/to/file.xlsx"],
    "timeout_seconds": 300
  }
  ```
- `GET /api/tasks/{task_id}` - Get task status
- `GET /api/output` - List output files

## Usage Examples

### Using Streamlit

1. Select files from folders or upload files
2. Enter your analysis prompt
3. Click "Submit" and wait for results
4. View and download generated files

### Using Vue.js Frontend

1. Open `http://localhost:5173`
2. Select files from folders or upload new files
3. Enter your analysis prompt
4. Click "Submit" and watch real-time progress
5. Download generated files when complete

### Using API Directly

```python
import requests

# Upload a file
with open('data.xlsx', 'rb') as f:
    response = requests.post('http://localhost:8000/api/upload', files={'file': f})
    file_info = response.json()

# Start analysis
analysis_request = {
    "prompt": "Analyze sales data and create monthly summary",
    "file_paths": [file_info['file']['path']],
    "timeout_seconds": 300
}
response = requests.post('http://localhost:8000/api/analyze', json=analysis_request)
task_id = response.json()['task_id']

# Check status
status = requests.get(f'http://localhost:8000/api/tasks/{task_id}').json()
print(status)
```

## Configuration

### Timeout Settings

Default timeout is 300 seconds (5 minutes). You can adjust it:
- In Streamlit: Use sidebar timeout settings
- In API: Pass `timeout_seconds` in the request
- In Vue.js: Currently uses 300 seconds (can be modified in `App.vue`)

### CORS Settings

FastAPI CORS is configured for:
- `http://localhost:5173` (Vite default)
- `http://localhost:3000` (Alternative port)
- `http://localhost:8080` (Alternative port)

To add more origins, edit `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "your-custom-origin"],
    ...
)
```

## Troubleshooting

### FastAPI Issues

**Problem: "ModuleNotFoundError: No module named 'uvicorn'"**
```bash
pip install uvicorn[standard]
```

**Problem: "Port 8000 already in use"**
Change the port in `run_api.bat` or command:
```bash
python -m uvicorn api.main:app --reload --port 8001
```

### Vue.js Issues

**Problem: "npm: command not found"**
Install Node.js from [nodejs.org](https://nodejs.org/)

**Problem: "Port 5173 already in use"**
Vite will automatically use the next available port, or edit `vite.config.js`

**Problem: "Cannot connect to API"**
- Make sure FastAPI is running on port 8000
- Check CORS settings in `api/main.py`
- Verify proxy settings in `frontend/vite.config.js`

### General Issues

See the original README section for Streamlit-specific troubleshooting.

## Development

### Adding New API Endpoints

1. Edit `api/main.py`
2. Add your route handler
3. Update Vue.js frontend if needed (`frontend/src/App.vue`)

### Customizing Vue.js Frontend

- Main component: `frontend/src/App.vue`
- Styles: `frontend/src/style.css`
- API configuration: `frontend/src/App.vue` (API_BASE constant)

## Deployment

### Streamlit Cloud
See original README for Streamlit Cloud deployment.

### FastAPI + Vue.js Deployment

1. **Backend**: Deploy FastAPI using:
   - Docker
   - Cloud platforms (Heroku, Railway, etc.)
   - VPS with gunicorn/uvicorn

2. **Frontend**: Build and deploy:
   ```bash
   cd frontend
   npm run build
   ```
   Deploy `dist/` folder to:
   - Netlify
   - Vercel
   - GitHub Pages
   - Any static hosting

3. **Update API URL**: Change `API_BASE` in `frontend/src/App.vue` to your production API URL

## Notes

- All three applications can run simultaneously
- They share the same `output/` and `uploads/` folders
- Make sure OpenAI API key is set in `.env` file
- FastAPI and Vue.js are designed to work together
- Streamlit app works independently
