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
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3>Uploaded Files</h3>
            <button 
              class="primary" 
              @click="previewAllFiles"
              style="padding: 8px 16px; font-size: 14px;"
            >
              👁️ File Preview
            </button>
          </div>
          <ul class="file-list">
            <li v-for="file in uploadedFiles" :key="file.path" class="file-item">
              <div class="file-info">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-path">{{ file.path }}</div>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <div v-if="activeTab === 'selected'" class="tab-content active">
        <div v-if="selectedFiles.length === 0" class="status warning">
          No files selected
        </div>
        <div v-else>
          <div class="status info" style="margin-bottom: 15px;">
            📊 {{ selectedFiles.length }} file(s) selected
          </div>
          <ul class="file-list">
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


    <!-- All Files Preview Modal with Tabs -->
    <div v-if="allFilesPreview && allFilesPreviewData" class="modal-overlay" @click.self="closeAllFilesPreview">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>📄 All Files Preview</h2>
          <button class="secondary" @click="closeAllFilesPreview" style="padding: 8px 16px; background: rgba(255, 255, 255, 0.2); color: white;">
            ❌ Close
          </button>
        </div>
        <div class="modal-body">
          <div class="status info" style="margin-bottom: 15px;">
            Previewing {{ Object.keys(allFilesPreviewData.files).length }} file(s). Use tabs below to switch between files.
          </div>
          
          <!-- Tabs for each file -->
          <div class="tabs" style="margin-bottom: 20px; overflow-x: auto;">
            <button 
              v-for="(fileData, filePath) in allFilesPreviewData.files" 
              :key="filePath"
              class="tab" 
              :class="{ active: activePreviewTab === filePath }"
              @click="activePreviewTab = filePath"
            >
              📊 {{ fileData.file_name || getFileName(filePath) }}
            </button>
          </div>

          <!-- Content for active tab -->
          <div v-for="(fileData, filePath) in allFilesPreviewData.files" :key="filePath">
            <div v-if="activePreviewTab === filePath">
              <div v-if="fileData.error" class="status error">
                Error loading {{ fileData.file_name }}: {{ fileData.error }}
              </div>
              <div v-else-if="fileData.type === 'excel'">
                <!-- Sheet tabs for Excel files -->
                <div v-if="Object.keys(fileData.sheets).length > 1" class="tabs" style="margin-bottom: 20px; overflow-x: auto;">
                  <button 
                    v-for="(sheet, sheetName) in fileData.sheets" 
                    :key="sheetName"
                    class="tab" 
                    :class="{ active: getActiveSheet(filePath) === sheetName }"
                    @click="setActiveSheet(filePath, sheetName)"
                  >
                    📋 {{ sheetName }}
                  </button>
                </div>
                
                <!-- Display active sheet -->
                <template v-if="getActiveSheet(filePath)">
                  <div :key="`${filePath}-${getActiveSheet(filePath)}`">
                    <template v-for="(sheet, sheetName) in fileData.sheets" :key="sheetName">
                      <div v-if="getActiveSheet(filePath) === sheetName">
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
                    </template>
                  </div>
                </template>
              </div>
              <div v-else>
                <div class="status info">
                  Rows: {{ fileData.rows }}, Columns: {{ fileData.columns }}
                </div>
                <div style="overflow-x: auto; margin-top: 15px;">
                  <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                      <tr>
                        <th v-for="col in fileData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                          {{ col }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in fileData.preview.slice(0, 10)" :key="idx">
                        <td v-for="col in fileData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                          {{ row[col] }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
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
      allFilesPreview: false,
      allFilesPreviewData: null,
      activePreviewTab: null,
      activeSheets: {} // Track active sheet for each file: { filePath: sheetName }
    }
  },
  computed: {
    canSubmit() {
      return this.selectedFiles.length > 0 && this.prompt.trim().length > 0 && !this.analyzing
    }
  },
  mounted() {
    this.loadFolders()
    // Add ESC key listener to close modal
    document.addEventListener('keydown', this.handleKeyDown)
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.handleKeyDown)
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
    async previewAllFiles() {
      if (this.selectedFiles.length === 0) {
        alert('No files selected')
        return
      }
      
      try {
        this.allFilesPreview = true
        const response = await axios.post(`${API_BASE}/files/preview`, {
          file_paths: this.selectedFiles
        })
        this.allFilesPreviewData = response.data
        // Set first file as active tab
        const firstFilePath = Object.keys(response.data.files)[0]
        this.activePreviewTab = firstFilePath
        
        // Initialize active sheets for each Excel file
        this.activeSheets = {}
        for (const [filePath, fileData] of Object.entries(response.data.files)) {
          if (fileData.type === 'excel' && fileData.sheets) {
            const firstSheet = Object.keys(fileData.sheets)[0]
            this.activeSheets[filePath] = firstSheet
          }
        }
      } catch (error) {
        console.error('Error previewing files:', error)
        alert('Error previewing files: ' + (error.response?.data?.detail || error.message))
        this.allFilesPreview = false
        this.allFilesPreviewData = null
      }
    },
    closeAllFilesPreview() {
      this.allFilesPreview = false
      this.allFilesPreviewData = null
      this.activePreviewTab = null
      this.activeSheets = {}
    },
    getActiveSheet(filePath) {
      if (this.activeSheets[filePath]) {
        return this.activeSheets[filePath]
      }
      // Default to first sheet if not set
      if (this.allFilesPreviewData?.files[filePath]?.sheets) {
        const firstSheet = Object.keys(this.allFilesPreviewData.files[filePath].sheets)[0]
        // Set it as active if not already set
        if (!this.activeSheets[filePath]) {
          this.$set(this.activeSheets, filePath, firstSheet)
        }
        return firstSheet
      }
      return null
    },
    setActiveSheet(filePath, sheetName) {
      // Create a new object to ensure reactivity
      this.activeSheets = {
        ...this.activeSheets,
        [filePath]: sheetName
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
    },
    handleKeyDown(event) {
      // Close modal on ESC key
      if (event.key === 'Escape' && this.allFilesPreview) {
        this.closeAllFilesPreview()
      }
    }
  }
}
</script>

