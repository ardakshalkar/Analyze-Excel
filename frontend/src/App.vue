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
        <button 
          class="tab" 
          :class="{ active: activeTab === 'preview' }"
          @click="handlePreviewTabClick"
        >
          👁️ Preview
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
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
              <h3 style="margin: 0;">📂 {{ folder.name }} ({{ folder.files.length }} file(s))</h3>
              <button 
                v-if="selectedFolders.includes(folder.name)"
                class="danger" 
                @click="removeFolder(folder.name)"
                style="padding: 8px 16px; font-size: 14px;"
              >
                Remove
              </button>
              <button 
                v-else
                class="primary" 
                @click="selectFolder(folder.name)"
                style="padding: 8px 16px; font-size: 14px;"
              >
                Select
              </button>
            </div>
            <div v-if="folder.files.length === 0" class="status info">
              No files in this folder
            </div>
            <div v-else>
              <div v-for="file in folder.files" :key="file.path" class="checkbox-item" style="display: flex; align-items: center; padding: 8px 0;">
                <input 
                  type="checkbox" 
                  :id="file.path"
                  :checked="selectedFiles.includes(file.path)"
                  disabled
                  style="margin-right: 10px;"
                />
                <label :for="file.path" style="margin: 0; cursor: default;">{{ file.name }}</label>
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
                <div class="file-path">
                  {{ filePath }}
                  <span v-if="getFileFolder(filePath)" style="color: #666; font-size: 12px;">
                    (from {{ getFileFolder(filePath) }})
                  </span>
                  <span v-else-if="isUploadedFile(filePath)" style="color: #666; font-size: 12px;">
                    (uploaded)
                  </span>
                </div>
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

      <div v-if="activeTab === 'preview'" class="tab-content active">
        <div v-if="selectedFiles.length === 0" class="status warning">
          No files selected. Please select files from folders or upload files to preview them.
        </div>
        <div v-else-if="loadingPreview" class="status info">
          Loading preview...
        </div>
        <div v-else-if="previewData && previewData.files">
          <div class="status info" style="margin-bottom: 15px;">
            Previewing {{ Object.keys(previewData.files).length }} file(s). Use tabs below to switch between files.
          </div>
          
          <!-- Tabs for each file -->
          <div class="tabs" style="margin-bottom: 20px; overflow-x: auto;">
            <button 
              v-for="(fileData, filePath) in previewData.files" 
              :key="filePath"
              class="tab" 
              :class="{ active: activePreviewTab === filePath }"
              @click="activePreviewTab = filePath"
            >
              📊 {{ fileData.file_name || getFileName(filePath) }}
            </button>
          </div>

          <!-- Content for active tab -->
          <div v-for="(fileData, filePath) in previewData.files" :key="filePath">
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
                        <div style="overflow-x: auto; margin-top: 15px; max-height: 600px; overflow-y: auto;">
                          <table style="width: 100%; border-collapse: collapse;">
                            <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                              <tr>
                                <th v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                                  {{ col }}
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="(row, idx) in sheet.preview" :key="idx">
                                <td v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                                  {{ row[col] }}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div v-if="sheet.preview.length < sheet.rows" class="status info" style="margin-top: 10px;">
                          Showing {{ sheet.preview.length }} of {{ sheet.rows }} rows
                        </div>
                      </div>
                    </template>
                  </div>
                </template>
              </div>
              <div v-else>
                <h3>{{ fileData.file_name }}</h3>
                <div class="status info">
                  Rows: {{ fileData.rows }}, Columns: {{ fileData.columns }}
                </div>
                <div style="overflow-x: auto; margin-top: 15px; max-height: 600px; overflow-y: auto;">
                  <table style="width: 100%; border-collapse: collapse;">
                    <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                      <tr>
                        <th v-for="col in fileData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                          {{ col }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in fileData.preview" :key="idx">
                        <td v-for="col in fileData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                          {{ row[col] }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="fileData.preview.length < fileData.rows" class="status info" style="margin-top: 10px;">
                  Showing {{ fileData.preview.length }} of {{ fileData.rows }} rows
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="status warning">
          Click on the Preview tab to load file previews.
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
      <div v-if="currentTask && (currentTask.result || streamingOutput || currentTask.status === 'running')" class="status success" style="margin-top: 15px;">
        <div v-if="currentTask.result" style="margin-bottom: 15px;">
          <h3>✅ Analysis Complete!</h3>
        </div>
        
        <!-- Tabs for Analysis Result and Thinking Process -->
        <div class="tabs" style="margin-top: 15px; margin-bottom: 15px;">
          <button 
            class="tab" 
            :class="{ active: currentTask.activeTab === 'result' || !currentTask.activeTab }"
            @click="currentTask.activeTab = 'result'"
          >
            📋 Analysis Result
          </button>
          <button 
            class="tab" 
            :class="{ active: currentTask.activeTab === 'thinking' }"
            @click="currentTask.activeTab = 'thinking'"
          >
            🧠 Thinking Process
            <span v-if="currentTask.status === 'running'" class="loading" style="display: inline-block; margin-left: 5px;"></span>
          </button>
        </div>
        
        <!-- Analysis Result Tab -->
        <div v-if="!currentTask.activeTab || currentTask.activeTab === 'result'">
          <div v-if="currentTask.result" style="margin-top: 15px;">
            <strong>Main Answer:</strong>
            <pre style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-top: 10px; white-space: pre-wrap;">{{ currentTask.result.main_answer }}</pre>
          </div>
          <div v-else-if="currentTask.status === 'running'" class="status info">
            Analysis in progress... Results will appear here when complete.
          </div>
          <div v-else class="status info">
            No results yet.
          </div>
        </div>
        
        <!-- Thinking Process Tab -->
        <div v-if="currentTask.activeTab === 'thinking'">
          <div style="margin-top: 15px;">
            <div v-if="streamingOutput || currentTask.result?.intermediate_steps" style="position: relative;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <strong>Thinking Process:</strong>
                <button 
                  @click="copyThinkingProcess"
                  class="secondary"
                  style="padding: 4px 8px; font-size: 12px;"
                >
                  📋 Copy
                </button>
              </div>
              <pre style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-top: 10px; white-space: pre-wrap; max-height: 600px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 12px;">{{ thinkingProcessText }}</pre>
            </div>
            <div v-else class="status info">
              No thinking process available yet.
            </div>
          </div>
        </div>
        
        <!-- Generated Files Section (shown in both tabs) -->
        <div v-if="currentTask.result && currentTask.result.generated_files && currentTask.result.generated_files.length > 0" style="margin-top: 15px;">
          <strong>Generated Files:</strong>
          <ul class="file-list" style="margin-top: 10px;">
            <li v-for="file in currentTask.result.generated_files" :key="file" class="file-item">
              <div class="file-info">
                <div class="file-name">{{ getFileName(file) }}</div>
              </div>
              <div style="display: flex; gap: 10px;">
                <button 
                  @click="previewGeneratedFile(file)"
                  style="padding: 6px 12px; font-size: 14px;"
                  class="primary"
                >
                  👁️ Preview
                </button>
                <a 
                  :href="`/api/download/${encodeURIComponent(file)}`" 
                  target="_blank"
                  style="text-decoration: none;"
                >
                  <button style="padding: 6px 12px; font-size: 14px;">
                    📥 Download
                  </button>
                </a>
              </div>
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
                        <div style="overflow-x: auto; margin-top: 15px; max-height: 600px; overflow-y: auto;">
                          <table style="width: 100%; border-collapse: collapse;">
                            <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                              <tr>
                                <th v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                                  {{ col }}
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="(row, idx) in sheet.preview" :key="idx">
                                <td v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                                  {{ row[col] }}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div v-if="sheet.preview.length < sheet.rows" class="status info" style="margin-top: 10px;">
                          Showing {{ sheet.preview.length }} of {{ sheet.rows }} rows
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
                      <tr v-for="(row, idx) in fileData.preview" :key="idx">
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

    <!-- Generated File Preview Modal -->
    <div v-if="generatedFilePreview && generatedFilePreviewData" class="modal-overlay" @click.self="closeGeneratedFilePreview">
      <div class="modal-content" @click.stop style="max-width: 95%; max-height: 95vh;">
        <div class="modal-header">
          <h2>📄 Preview: {{ getFileName(generatedFilePreviewPath) }}</h2>
          <button class="secondary" @click="closeGeneratedFilePreview" style="padding: 8px 16px; background: rgba(255, 255, 255, 0.2); color: white;">
            ❌ Close
          </button>
        </div>
        <div class="modal-body" style="max-height: calc(95vh - 120px); overflow-y: auto;">
          <div v-if="loadingGeneratedPreview" class="status info">
            Loading preview...
          </div>
          <div v-else-if="generatedFilePreviewData.error" class="status error">
            Error: {{ generatedFilePreviewData.error }}
          </div>
          <div v-else-if="generatedFilePreviewData.type === 'excel'">
            <!-- Sheet tabs for Excel files -->
            <div v-if="Object.keys(generatedFilePreviewData.sheets).length > 1" class="tabs" style="margin-bottom: 20px; overflow-x: auto;">
              <button 
                v-for="(sheet, sheetName) in generatedFilePreviewData.sheets" 
                :key="sheetName"
                class="tab" 
                :class="{ active: getActiveSheet(generatedFilePreviewPath) === sheetName }"
                @click="setActiveSheet(generatedFilePreviewPath, sheetName)"
              >
                📋 {{ sheetName }}
              </button>
            </div>
            
            <!-- Display active sheet -->
            <template v-if="getActiveSheet(generatedFilePreviewPath)">
              <div :key="`${generatedFilePreviewPath}-${getActiveSheet(generatedFilePreviewPath)}`">
                <template v-for="(sheet, sheetName) in generatedFilePreviewData.sheets" :key="sheetName">
                  <div v-if="getActiveSheet(generatedFilePreviewPath) === sheetName">
                    <h3>Sheet: {{ sheetName }}</h3>
                    <div class="status info">
                      Rows: {{ sheet.rows }}, Columns: {{ sheet.columns }}
                    </div>
                    <div style="overflow-x: auto; margin-top: 15px; max-height: 70vh; overflow-y: auto;">
                      <table style="width: 100%; border-collapse: collapse;">
                        <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                          <tr>
                            <th v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                              {{ col }}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(row, idx) in sheet.preview" :key="idx">
                            <td v-for="col in sheet.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                              {{ row[col] }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-if="sheet.preview.length < sheet.rows" class="status info" style="margin-top: 10px;">
                      Showing {{ sheet.preview.length }} of {{ sheet.rows }} rows
                    </div>
                  </div>
                </template>
              </div>
            </template>
          </div>
          <div v-else>
            <h3>{{ getFileName(generatedFilePreviewPath) }}</h3>
            <div class="status info">
              Rows: {{ generatedFilePreviewData.rows }}, Columns: {{ generatedFilePreviewData.columns }}
            </div>
            <div style="overflow-x: auto; margin-top: 15px; max-height: 70vh; overflow-y: auto;">
              <table style="width: 100%; border-collapse: collapse;">
                <thead style="position: sticky; top: 0; background: #f8f9fa; z-index: 10;">
                  <tr>
                    <th v-for="col in generatedFilePreviewData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd; background: #f8f9fa;">
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in generatedFilePreviewData.preview" :key="idx">
                    <td v-for="col in generatedFilePreviewData.column_names" :key="col" style="padding: 8px; border: 1px solid #ddd;">
                      {{ row[col] }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="generatedFilePreviewData.preview.length < generatedFilePreviewData.rows" class="status info" style="margin-top: 10px;">
              Showing {{ generatedFilePreviewData.preview.length }} of {{ generatedFilePreviewData.rows }} rows
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
      selectedFolders: [], // Track which folders are selected
      uploadedFiles: [],
      prompt: '',
      analyzing: false,
      currentTask: null,
      taskPollInterval: null,
      streamingOutput: '', // For streaming responses
      useStreaming: true, // Toggle for streaming vs polling
      allFilesPreview: false,
      allFilesPreviewData: null,
      activePreviewTab: null,
      activeSheets: {}, // Track active sheet for each file: { filePath: sheetName }
      loadingPreview: false,
      previewData: null, // Preview data for the Preview tab
      generatedFilePreview: false,
      generatedFilePreviewData: null,
      generatedFilePreviewPath: null,
      loadingGeneratedPreview: false
    }
  },
  computed: {
    canSubmit() {
      return this.selectedFiles.length > 0 && this.prompt.trim().length > 0 && !this.analyzing
    },
    thinkingProcessText() {
      if (this.currentTask?.result?.intermediate_steps) {
        return this.currentTask.result.intermediate_steps
      }
      return this.streamingOutput || ''
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
    async handlePreviewTabClick() {
      this.activeTab = 'preview'
      
      if (this.selectedFiles.length === 0) {
        return
      }
      
      // Load preview if not already loaded or if files changed
      if (!this.previewData || this.hasFilesChanged()) {
        await this.loadPreview()
      }
    },
    hasFilesChanged() {
      if (!this.previewData || !this.previewData.files) {
        return true
      }
      const previewFilePaths = Object.keys(this.previewData.files)
      if (previewFilePaths.length !== this.selectedFiles.length) {
        return true
      }
      return !this.selectedFiles.every(path => previewFilePaths.includes(path))
    },
    async loadPreview() {
      if (this.selectedFiles.length === 0) {
        return
      }
      
      this.loadingPreview = true
      try {
        const response = await axios.post(`${API_BASE}/files/preview`, {
          file_paths: this.selectedFiles
        })
        this.previewData = response.data
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
        console.error('Error loading preview:', error)
        alert('Error loading preview: ' + (error.response?.data?.detail || error.message))
        this.previewData = null
      } finally {
        this.loadingPreview = false
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
    async previewGeneratedFile(filePath) {
      this.generatedFilePreview = true
      this.generatedFilePreviewPath = filePath
      this.loadingGeneratedPreview = true
      
      try {
        const response = await axios.get(`${API_BASE}/files/${encodeURIComponent(filePath)}/preview`)
        this.generatedFilePreviewData = response.data
        
        // Initialize active sheet for Excel files
        if (response.data.type === 'excel' && response.data.sheets) {
          const firstSheet = Object.keys(response.data.sheets)[0]
          this.activeSheets[filePath] = firstSheet
        }
      } catch (error) {
        console.error('Error loading generated file preview:', error)
        this.generatedFilePreviewData = {
          error: error.response?.data?.detail || error.message || 'Failed to load preview'
        }
      } finally {
        this.loadingGeneratedPreview = false
      }
    },
    closeGeneratedFilePreview() {
      this.generatedFilePreview = false
      this.generatedFilePreviewData = null
      this.generatedFilePreviewPath = null
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
    selectFolder(folderName) {
      const folder = this.folders.find(f => f.name === folderName)
      if (!folder) return
      
      // Add all files from folder to selectedFiles
      folder.files.forEach(file => {
        if (!this.selectedFiles.includes(file.path)) {
          this.selectedFiles.push(file.path)
        }
      })
      
      // Mark folder as selected
      if (!this.selectedFolders.includes(folderName)) {
        this.selectedFolders.push(folderName)
      }
    },
    removeFolder(folderName) {
      const folder = this.folders.find(f => f.name === folderName)
      if (!folder) return
      
      // Remove all files from this folder from selectedFiles
      folder.files.forEach(file => {
        this.selectedFiles = this.selectedFiles.filter(f => f !== file.path)
      })
      
      // Remove folder from selectedFolders
      this.selectedFolders = this.selectedFolders.filter(f => f !== folderName)
    },
    removeFile(filePath) {
      this.selectedFiles = this.selectedFiles.filter(f => f !== filePath)
      this.uploadedFiles = this.uploadedFiles.filter(f => f.path !== filePath)
      
      // Also remove from selectedFolders if all files from that folder are removed
      this.folders.forEach(folder => {
        const folderFiles = folder.files.map(f => f.path)
        const hasSelectedFiles = folderFiles.some(path => this.selectedFiles.includes(path))
        if (!hasSelectedFiles && this.selectedFolders.includes(folder.name)) {
          this.selectedFolders = this.selectedFolders.filter(f => f !== folder.name)
        }
      })
    },
    getFileName(filePath) {
      return filePath.split(/[/\\]/).pop()
    },
    getFileFolder(filePath) {
      // Find which folder this file belongs to
      for (const folder of this.folders) {
        if (folder.files.some(f => f.path === filePath)) {
          return folder.name
        }
      }
      return null
    },
    isUploadedFile(filePath) {
      return this.uploadedFiles.some(f => f.path === filePath)
    },
    async submitAnalysis() {
      if (!this.canSubmit) return
      
      this.analyzing = true
      this.currentTask = null
      this.streamingOutput = ''
      
      if (this.useStreaming) {
        // Use streaming endpoint
        await this.submitAnalysisStream()
      } else {
        // Use polling endpoint
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
          alert('Error starting analysis: ' + (error.response?.data?.detail || error.message))
          this.analyzing = false
        }
      }
    },
    async submitAnalysisStream() {
      try {
        const response = await fetch(`${API_BASE}/analyze/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            prompt: this.prompt,
            file_paths: this.selectedFiles,
            timeout_seconds: 300
          })
        })
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        
        // Initialize task
        this.currentTask = {
          task_id: null,
          status: 'running',
          progress: 0,
          result: null,
          error: null
        }
        
        while (true) {
          const { done, value } = await reader.read()
          
          if (done) {
            break
          }
          
          // Decode chunk
          buffer += decoder.decode(value, { stream: true })
          
          // Process complete SSE messages
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                this.handleStreamEvent(data)
              } catch (e) {
                console.error('Error parsing SSE data:', e, line)
              }
            }
          }
        }
        
        // Process remaining buffer
        if (buffer.trim()) {
          const lines = buffer.split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))
                this.handleStreamEvent(data)
              } catch (e) {
                console.error('Error parsing SSE data:', e, line)
              }
            }
          }
        }
        
        this.analyzing = false
      } catch (error) {
        console.error('Error in streaming analysis:', error)
        alert('Error in streaming analysis: ' + error.message)
        this.analyzing = false
        if (this.currentTask) {
          this.currentTask.status = 'error'
          this.currentTask.error = error.message
        }
      }
    },
    handleStreamEvent(data) {
      switch (data.type) {
        case 'status':
          if (data.task_id) {
            this.currentTask.task_id = data.task_id
          }
          if (data.status) {
            this.currentTask.status = data.status
          }
          if (data.progress !== undefined) {
            this.currentTask.progress = data.progress
          }
          break
        case 'progress':
          if (data.progress !== undefined) {
            this.currentTask.progress = data.progress
          }
          break
        case 'chunk':
        case 'output':
          // Append streaming output
          if (data.content) {
            this.streamingOutput += data.content
            // Update intermediate steps in result if it exists
            if (this.currentTask.result) {
              this.currentTask.result.intermediate_steps = this.streamingOutput
            }
          }
          break
        case 'result':
          this.currentTask.result = data.result
          break
        case 'error':
          this.currentTask.status = 'error'
          this.currentTask.error = data.error
          this.analyzing = false
          break
        case 'heartbeat':
          // Just keep connection alive
          break
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
      this.selectedFolders = []
      this.uploadedFiles = []
      this.prompt = ''
      this.currentTask = null
      this.previewData = null
      this.activePreviewTab = null
      this.activeSheets = {}
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
      if (event.key === 'Escape') {
        if (this.allFilesPreview) {
          this.closeAllFilesPreview()
        } else if (this.generatedFilePreview) {
          this.closeGeneratedFilePreview()
        }
      }
    },
    copyThinkingProcess() {
      const text = this.thinkingProcessText
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          alert('Thinking process copied to clipboard!')
        }).catch(err => {
          console.error('Failed to copy:', err)
          // Fallback: select text
          const textarea = document.createElement('textarea')
          textarea.value = text
          document.body.appendChild(textarea)
          textarea.select()
          document.execCommand('copy')
          document.body.removeChild(textarea)
          alert('Thinking process copied to clipboard!')
        })
      }
    }
  }
}
</script>

