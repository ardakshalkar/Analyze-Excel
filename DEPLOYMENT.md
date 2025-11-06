# Deployment Guide for Analyze & Excel

## Local Installation

The interpreter is a Python package (`open-interpreter`) that gets installed automatically when you install dependencies.

### Steps:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your OpenAI API key:**
   - Create a `.env` file in the root directory
   - Add: `OPENAI_API_KEY=your_api_key_here`
   - Or set it as an environment variable

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

That's it! The interpreter is included in the package installation.

## Streamlit Cloud Deployment

### ⚠️ IMPORTANT: Python Version Requirement

**Before deploying, you MUST set Python version to 3.12 (or 3.11) in Streamlit Cloud settings!**

- Streamlit Cloud defaults to Python 3.13, which is **NOT compatible** with `tiktoken` (required by `open-interpreter`)
- Python 3.13 support for `tiktoken` is not available yet (PyO3 doesn't support Python 3.13)
- **Solution:** Go to your app Settings → Change Python version to **3.12** → Save and redeploy
- See detailed instructions in the "Troubleshooting" section below

### Important Considerations:

⚠️ **Streamlit Community Cloud has limitations:**
- Code execution may be restricted for security reasons
- File system access is limited
- Some system commands may not work

However, `open-interpreter` should work for most use cases since it primarily uses OpenAI's API and executes Python code in memory.

### Steps to Deploy on Streamlit Cloud:

1. **Push your code to GitHub:**
   - Make sure your repository is public (or you have Streamlit Cloud Pro)
   - Include `requirements.txt` in the repository
   - Include `runtime.txt` to pin Python version (recommended: Python 3.12 for better compatibility)

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository and branch
   - Set main file path: `app.py`
   - **IMPORTANT:** Before deploying, go to "Advanced settings" or "Settings" and set Python version to **3.12** (or 3.11) to avoid `tiktoken` build errors

3. **Set Secrets (API Key):**
   - In Streamlit Cloud, go to your app settings
   - Click "Secrets" tab
   - Add your OpenAI API key:
     ```toml
     OPENAI_API_KEY = "your_api_key_here"
     ```
   - Optionally set timeout:
     ```toml
     TIMEOUT_SECONDS = "300"
     ```

4. **Deploy:**
   - Click "Deploy"
   - Wait for the build to complete

### Troubleshooting Streamlit Cloud:

If you encounter issues:

1. **Check logs:** Look at the deployment logs for errors
2. **Verify secrets:** Make sure `OPENAI_API_KEY` is set correctly
3. **Test locally first:** Ensure everything works locally before deploying
4. **Check timeout:** Increase `TIMEOUT_SECONDS` if operations are timing out

#### Common Error: "Failed building wheel for tiktoken"

**⚠️ CRITICAL: This error occurs because Streamlit Cloud is using Python 3.13, which is NOT supported by `tiktoken`.**

**Root Cause:**
- Python 3.13 was released recently (October 2024)
- `tiktoken` uses PyO3 (Rust-Python bridge) which doesn't support Python 3.13 yet
- Without prebuilt wheels, pip tries to build from source, requiring Rust compiler
- Streamlit Cloud doesn't provide Rust compiler, so the build fails

**✅ SOLUTION: You MUST manually set Python version to 3.12 in Streamlit Cloud**

**Step-by-Step Instructions:**

1. **Go to Streamlit Cloud Dashboard:**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Sign in and go to your app

2. **Access App Settings:**
   - Click on your app name
   - Click the **"⚙️ Settings"** button (top right, next to "Manage app")
   - OR click the **"⋮" (three dots)** menu → **"Settings"**

3. **Change Python Version:**
   - Scroll down to **"Python version"** section
   - You'll see a dropdown showing the current version (likely 3.13)
   - **Change it to Python 3.12** (or 3.11 as fallback)
   - Click **"Save"**

4. **Redeploy:**
   - After saving, the app will automatically redeploy
   - OR click **"Reboot app"** or **"Redeploy"** button
   - Wait for the build to complete

5. **Verify:**
   - Check the deployment logs
   - You should see Python 3.12 in the build output
   - The `tiktoken` installation should succeed

**Why This Works:**
- Python 3.12 has prebuilt wheels for `tiktoken` 0.7.x
- No Rust compiler needed
- Compatible with `open-interpreter` requirements

**Additional Notes:**
- `runtime.txt` file exists but Streamlit Cloud may not automatically use it
- Manual setting in UI is the most reliable method
- `tiktoken>=0.7.0,<0.8.0` in requirements.txt ensures compatibility with `open-interpreter`

### Alternative Hosting Options:

If Streamlit Cloud doesn't work well, consider:

1. **Heroku** (with Docker)
2. **Railway**
3. **Render**
4. **AWS/GCP/Azure** (with Docker containers)
5. **DigitalOcean App Platform**

These platforms offer more control over the environment and may better support code execution.

## Docker Deployment (Alternative)

If you want more control, you can use Docker:

1. Create a `Dockerfile`:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   EXPOSE 8501

   CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
   ```

2. Build and run:
   ```bash
   docker build -t analyze-excel .
   docker run -p 8501:8501 -e OPENAI_API_KEY=your_key analyze-excel
   ```

## Summary

- **Local:** Just install requirements.txt - the interpreter is included!
- **Streamlit Cloud:** Should work, but test thoroughly. Set secrets for API key.
- **Docker/Other platforms:** More control, better for production use.

