<template>
  <div id="app">
    <div class="container">
      <h1>📊 Analyze & Excel</h1>
      <p>Upload or select files and analyze them with AI-powered code interpreter</p>
    </div>

    <div class="container">
      <h2>📁 File Selection</h2>
      
      <div class="tabs">
        <button 
          class="tab" 
          :class="{ active: activeTab === 'folders' }"
          @click="activeTab = 'folders'"
        >
          📂 Folders
        </button>
        <button 
          class="tab" 
          :class="{ active: activeTab === 'upload' }"
          @click="activeTab = 'upload'"
        >
          ⬆️ Upload
        </button>
        <button 
          class="tab" 
          :class="{ active: activeTab === 'selected' }"
          @click="activeTab = 'selected'"
        >
          ✅ Selected ({{ selectedFiles.length }})
        </button>
      </div>

      <div v-if="activeTab === 'folders'" class="tab-content active">
        <div v-if="loadingFolders" class="status info">
          Loading folders...
        </div>
        <div v-else-if="folders.length === 0" class="status warning">
          No predefined folders found. You can create folders like 'input_folder_1', 'input_folder_2', etc.
        </div>
        <div v-else>
          <div v-for="folder in folders" :key="folder.name" class="card">
            <h3>{{ folder.name }}</h3>
            <div v-if="folder.files.length === 0" class="status info">
              No files in this folder
            </div>
            <div v-else class="checkbox-group">
              <div 
                v-for="file in folder.files" 
                :key="file.path"
                class="checkbox-item"
              >
                <input 
                  type="checkbox" 
                  :id="file.path"
                  :value="file.path"
                  v-model="selectedFiles"
                />
                <label :for="file.path">{{ file.name }}</label>
                <button 
                  class="secondary" 
                  @click="previewFile(file.path)"
                  style="padding: 6px 12px; font-size: 14px;"
                >
                  👁️ Preview
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'upload'" class="tab-content active">
        <input 
          type="file" 
          @change="handleFileUpload" 
          accept=".xlsx,.xls,.csv"
          multiple
        />
        <div v-if="uploadedFiles.length > 0" style="margin-top: 20px;">
          <h3>Uploaded Files</h3>
          <ul class="file-list">
            <li v-for="file in uploadedFiles" :key="file.path" class="file-item">
              <div class="file-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-path">{{ file.path }}</div>
              </div>
              <div class="file-actions">
                <button 
                  class="secondary" 
                  @click="previewFile(file.path)"
                  style="padding: 6px 12px; font-size: 14px;"
                >
                  👁️ Preview
                </button>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="activeTab === 'selected'" class="tab-content active">
        <div v-if="selectedFiles.length === 0" class="status warning">
          No files selected
        </div>
        <ul v-else class="file-list">
          <li v-for="filePath in selectedFiles" :key="filePath" class="file-item">
            <div class="file-info">
              <div class="file-name">{{ getFileName(filePath) }}</div>
              <div class="file-path">{{ filePath }}</div>
            </div>
            <button 
              class="danger" 
              @click="removeFile(filePath)"
              style="padding: 6px 12px; font-size: 14px;"
            >
              ❌ Remove
            </button>
          </li>
        </ul>
      </div>
    </div>

    <div class="container">
      <h2>💬 Enter Your Prompt</h2>
      <textarea 
        v-model="prompt" 
        placeholder="Example: Analyze the sales data and create a summary report with monthly totals..."
      ></textarea>
      <div style="margin-top: 15px; display: flex; gap: 10px;">
        <button @click="submitAnalysis" :disabled="!canSubmit || analyzing">
          <span v-if="analyzing" class="loading"></span>
          {{ analyzing ? 'Analyzing...' : '🚀 Submit' }}
        </button>
        <button class="secondary" @click="clearAll" :disabled="analyzing">
          🗑️ Clear
        </button>
      </div>
    </div>

    <div v-if="currentTask" class="container">
      <h2>📊 Analysis Status</h2>
      <div class="status" :class="getStatusClass(currentTask.status)">
        Status: {{ currentTask.status }}
      </div>
      <div v-if="currentTask.progress !== null" class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: (currentTask.progress * 100) + '%' }"
        >
          {{ Math.round(currentTask.progress * 100) }}%
        </div>
      </div>
      <div v-if="currentTask.error" class="status error">
        Error: {{ currentTask.error }}
      </div>
      <div v-if="currentTask.result" class="status success">
        <h3>✅ Analysis Complete!</h3>
        <div style="margin-top: 15px;">
          <strong>Main Answer:</strong>
          <pre style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-top: 10px; white-space: pre-wrap;">{{ currentTask.result.main_answer }}</pre>
        </div>
        <div v-if="currentTask.result.generated_files && currentTask.result.generated_files.length > 0" style="margin-top: 15px;">
          <strong>Generated Files:</strong>
          <ul class="file-list" style="margin-top: 10px;">
            <li v-for="file in currentTask.result.generated_files" :key="file" class="file-item">
              <div class="file-info">
                <div class="file-name">{{ getFileName(file) }}</div>
              </div>
              <a 
                :href="`/api/download/${encodeURIComponent(file)}`" 
                target="_blank"
                style="text-decoration: none;"
              >
                <button style="padding: 6px 12px; font-size: 14px;">
                  📥 Download
                </button>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div v-if="previewData" class="container">
      <h2>👁️ File Preview</h2>
      <button class="secondary" @click="previewData = null" style="margin-bottom: 15px;">
        ❌ Close Preview
      </button>
      <div v-if="previewData.type === 'excel'">
        <div v-for="(sheet, sheetName) in previewData.sheets" :key="sheetName">
          <h3>Sheet: {{ sheetName }}</h3>
          <div class="status info">
            Rows: {{ sheet.rows }}, Columns: {{ sheet.columns }}
          </div>
          <div style="overflow-x: auto; margin-top: 15px;">
            <table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr>
                  <th v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                    {{ col }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in sheet.preview.slice(0, 10)" :key="idx">
                  <td v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                    {{ row[col] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div v-else>
        <div class="status info">
          Rows: {{ previewData.rows }}, Columns: {{ previewData.columns }}
        </div>
        <div style="overflow-x: auto; margin-top: 15px;">
          <table style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr>
                <th v-for="col in previewData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                  {{ col }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in previewData.preview.slice(0, 10)" :key="idx">
                <td v-for="col in previewData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                  {{ row[col] }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

const API_BASE = '/api'

export default {
  name: 'App',
  data() {
    return {
      activeTab: 'folders',
      folders: [],
      loadingFolders: false,
      selectedFiles: [],
      uploadedFiles: [],
      prompt: '',
      analyzing: false,
      currentTask: null,
      taskPollInterval: null,
      previewData: null
    }
  },
  computed: {
    canSubmit() {
      return this.selectedFiles.length > 0 && this.prompt.trim().length > 0 && !this.analyzing
    }
  },
  mounted() {
    this.loadFolders()
  },
  beforeUnmount() {
    if (this.taskPollInterval) {
      clearInterval(this.taskPollInterval)
    }
  },
  methods: {
    async loadFolders() {
      this.loadingFolders = true
      try {
        const response = await axios.get(`${API_BASE}/folders`)
        this.folders = response.data.folders
      } catch (error) {
        console.error('Error loading folders:', error)
      } finally {
        this.loadingFolders = false
      }
    },
    async handleFileUpload(event) {
      const files = event.target.files
      for (let file of files) {
        const formData = new FormData()
        formData.append('file', file)
        try {
          const response = await axios.post(`${API_BASE}/upload`, formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          })
          this.uploadedFiles.push(response.data.file)
          if (!this.selectedFiles.includes(response.data.file.path)) {
            this.selectedFiles.push(response.data.file.path)
          }
        } catch (error) {
          console.error('Error uploading file:', error)
          alert('Error uploading file: ' + error.response?.data?.detail || error.message)
        }
      }
    },
    async previewFile(filePath) {
      try {
        const response = await axios.get(`${API_BASE}/files/${encodeURIComponent(filePath)}/preview`)
        this.previewData = response.data
        this.activeTab = 'selected'
      } catch (error) {
        console.error('Error previewing file:', error)
        alert('Error previewing file: ' + error.response?.data?.detail || error.message)
      }
    },
    removeFile(filePath) {
      this.selectedFiles = this.selectedFiles.filter(f => f !== filePath)
      this.uploadedFiles = this.uploadedFiles.filter(f => f.path !== filePath)
    },
    getFileName(filePath) {
      return filePath.split(/[/\\]/).pop()
    },
    async submitAnalysis() {
      if (!this.canSubmit) return
      
      this.analyzing = true
      this.currentTask = null
      
      try {
        const response = await axios.post(`${API_BASE}/analyze`, {
          prompt: this.prompt,
          file_paths: this.selectedFiles,
          timeout_seconds: 300
        })
        
        const taskId = response.data.task_id
        this.currentTask = {
          task_id: taskId,
          status: 'pending',
          progress: 0
        }
        
        // Start polling for task status
        this.startPolling(taskId)
      } catch (error) {
        console.error('Error starting analysis:', error)
        alert('Error starting analysis: ' + error.response?.data?.detail || error.message)
        this.analyzing = false
      }
    },
    startPolling(taskId) {
      if (this.taskPollInterval) {
        clearInterval(this.taskPollInterval)
      }
      
      this.taskPollInterval = setInterval(async () => {
        try {
          const response = await axios.get(`${API_BASE}/tasks/${taskId}`)
          this.currentTask = response.data
          
          if (response.data.status === 'completed' || response.data.status === 'error') {
            clearInterval(this.taskPollInterval)
            this.analyzing = false
            this.taskPollInterval = null
          }
        } catch (error) {
          console.error('Error polling task status:', error)
          clearInterval(this.taskPollInterval)
          this.analyzing = false
          this.taskPollInterval = null
        }
      }, 2000) // Poll every 2 seconds
    },
    clearAll() {
      this.selectedFiles = []
      this.uploadedFiles = []
      this.prompt = ''
      this.currentTask = null
      if (this.taskPollInterval) {
        clearInterval(this.taskPollInterval)
        this.taskPollInterval = null
      }
      this.analyzing = false
    },
    getStatusClass(status) {
      const classes = {
        'pending': 'info',
        'running': 'info',
        'completed': 'success',
        'error': 'error'
      }
      return classes[status] || 'info'
    }
  }
}
</script>

