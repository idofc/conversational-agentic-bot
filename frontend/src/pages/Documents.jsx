import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import './Documents.css'

const API_BASE_URL = 'http://localhost:8000'

function Documents() {
  const { 'usecase-id': useCaseId } = useParams()
  const navigate = useNavigate()
  const [useCaseData, setUseCaseData] = useState(null)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  useEffect(() => {
    fetchUseCaseDetails()
    fetchDocuments()
  }, [useCaseId])

  const fetchUseCaseDetails = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}`)
      if (!response.ok) {
        throw new Error('Use case not found')
      }
      const data = await response.json()
      setUseCaseData(data)
    } catch (err) {
      console.error('Error fetching use case details:', err)
      setError(err.message)
    }
  }

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}/documents`)
      if (!response.ok) {
        throw new Error('Failed to fetch documents')
      }
      const data = await response.json()
      setDocuments(data)
    } catch (err) {
      console.error('Error fetching documents:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    try {
      setUploading(true)
      setUploadProgress(0)

      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error('Failed to upload document')
      }

      // Simulate progress
      setUploadProgress(100)
      
      // Refresh documents list
      setTimeout(() => {
        fetchDocuments()
        setUploading(false)
        setUploadProgress(0)
        e.target.value = '' // Reset file input
      }, 500)
    } catch (err) {
      console.error('Error uploading document:', err)
      setError(err.message)
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const handleDeleteDocument = async (documentId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) {
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}/documents/${documentId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete document')
      }

      // Refresh documents list
      fetchDocuments()
    } catch (err) {
      console.error('Error deleting document:', err)
      setError(err.message)
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString()
  }

  if (loading && documents.length === 0) {
    return <div className="loading">Loading documents...</div>
  }

  return (
    <div className="documents-page">
      <div className="documents-actions">
        <button 
          className="go-to-chat-btn" 
          onClick={() => navigate(`/usecase/${useCaseId}`)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          Go to Chat
        </button>
      </div>
      <div className="upload-section">
        <div className="upload-card">
          <h2>Upload New Document</h2>
          <div className="upload-area">
            <input
              type="file"
              id="file-upload"
              onChange={handleFileUpload}
              disabled={uploading}
              accept=".pdf,.doc,.docx,.txt"
            />
            <label htmlFor="file-upload" className={uploading ? 'disabled' : ''}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>{uploading ? 'Uploading...' : 'Choose a file or drag it here'}</span>
              <span className="file-types">Supported: PDF, DOC, DOCX, TXT</span>
            </label>
            {uploading && (
              <div className="upload-progress">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                </div>
                <span>{uploadProgress}%</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="documents-list-section">
        <h2>Uploaded Documents ({documents.length})</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        {documents.length === 0 ? (
          <div className="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
              <polyline points="13 2 13 9 20 9" />
            </svg>
            <p>No documents uploaded yet</p>
            <p className="empty-hint">Upload your first document to get started</p>
          </div>
        ) : (
          <div className="documents-grid">
            {documents.map(doc => (
              <div key={doc.id} className="document-card">
                <div className="document-icon">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                    <polyline points="13 2 13 9 20 9" />
                  </svg>
                </div>
                <div className="document-info">
                  <h3 className="document-name" title={doc.filename}>{doc.filename}</h3>
                  <div className="document-meta">
                    <span className="file-size">{formatFileSize(doc.file_size)}</span>
                    <span className="separator">•</span>
                    <span className="upload-date">{formatDate(doc.uploaded_at)}</span>
                  </div>
                  <div className="document-status">
                    <span className={`status-badge ${doc.status}`}>{doc.status}</span>
                  </div>
                </div>
                <div className="document-actions">
                  <button
                    className="delete-btn"
                    onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                    title="Delete document"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <line x1="10" y1="11" x2="10" y2="17" />
                      <line x1="14" y1="11" x2="14" y2="17" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Documents
