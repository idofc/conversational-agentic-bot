import { useState } from 'react'
import './UploadModal.css'

const API_BASE_URL = 'http://localhost:8000'

function UploadModal({ isOpen, onClose, useCaseUri }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')
  const [documents, setDocuments] = useState([])
  const [loadingDocs, setLoadingDocs] = useState(false)

  const handleFileSelect = (event) => {
    setSelectedFile(event.target.files[0])
    setUploadStatus('')
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a file')
      return
    }

    setUploading(true)
    setUploadStatus('Uploading...')

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseUri}/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const result = await response.json()
      setUploadStatus(`✓ ${result.message}. Processing...`)
      setSelectedFile(null)
      
      // Refresh document list
      await fetchDocuments()
    } catch (error) {
      setUploadStatus(`✗ Error: ${error.message}`)
    } finally {
      setUploading(false)
    }
  }

  const fetchDocuments = async () => {
    if (!useCaseUri) return
    
    setLoadingDocs(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseUri}/documents`)
      if (response.ok) {
        const data = await response.json()
        setDocuments(data)
      }
    } catch (error) {
      console.error('Error fetching documents:', error)
    } finally {
      setLoadingDocs(false)
    }
  }

  // Fetch documents when modal opens
  useState(() => {
    if (isOpen && useCaseUri) {
      fetchDocuments()
    }
  }, [isOpen, useCaseUri])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Upload Documents</h2>
          <button className="close-button" onClick={onClose}>&times;</button>
        </div>

        <div className="modal-body">
          <div className="upload-section">
            <div className="file-input-wrapper">
              <input
                type="file"
                id="file-input"
                accept=".pdf,.txt,.md"
                onChange={handleFileSelect}
                disabled={uploading}
              />
              <label htmlFor="file-input" className="file-input-label">
                {selectedFile ? selectedFile.name : 'Choose file (PDF, TXT, MD)'}
              </label>
            </div>

            <button
              className="upload-button"
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>

            {uploadStatus && (
              <div className={`upload-status ${uploadStatus.startsWith('✗') ? 'error' : 'success'}`}>
                {uploadStatus}
              </div>
            )}
          </div>

          <div className="documents-section">
            <h3>Uploaded Documents</h3>
            {loadingDocs ? (
              <p>Loading documents...</p>
            ) : documents.length === 0 ? (
              <p className="no-documents">No documents uploaded yet</p>
            ) : (
              <ul className="documents-list">
                {documents.map((doc) => (
                  <li key={doc.id} className="document-item">
                    <div className="document-info">
                      <span className="document-name">{doc.filename}</span>
                      <span className="document-size">
                        {(doc.file_size / 1024).toFixed(2)} KB
                      </span>
                    </div>
                    <span className={`document-status status-${doc.status}`}>
                      {doc.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default UploadModal
