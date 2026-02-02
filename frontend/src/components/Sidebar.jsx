import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import ConfirmModal from './ConfirmModal'
import './Sidebar.css'

const API_BASE_URL = 'http://localhost:8000'

function Sidebar({ isOpen, onClose, useCaseId }) {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    if (isOpen && useCaseId) {
      fetchConversations()
    }
  }, [isOpen, useCaseId])

  const fetchConversations = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}/conversations`)
      if (!response.ok) {
        throw new Error('Failed to fetch conversations')
      }
      const data = await response.json()
      setConversations(data.slice(0, 10)) // Get last 10 conversations
    } catch (err) {
      console.error('Error fetching conversations:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleManageDocuments = () => {
    navigate(`/usecase/${useCaseId}/documents`)
    onClose()
  }

  const handleConversationSelect = (conversationId) => {
    navigate(`/usecase/${useCaseId}/conversation/${conversationId}`)
    onClose()
  }

  const handleNewConversation = () => {
    onClose()
    // Navigate with query parameter to indicate new conversation
    window.location.href = `/usecase/${useCaseId}?new=true`
  }

  const handleDeleteConversation = (e, conversationId) => {
    e.stopPropagation() // Prevent triggering conversation selection
    setConversationToDelete(conversationId)
    setDeleteModalOpen(true)
  }

  const confirmDelete = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationToDelete}`, {
        method: 'DELETE'
      })
      
      if (!response.ok) {
        throw new Error('Failed to delete conversation')
      }
      
      // Refresh the conversation list
      await fetchConversations()
      
      // If the deleted conversation is currently open, navigate to use case home
      if (window.location.pathname.includes(`/conversation/${conversationToDelete}`)) {
        window.location.href = `/usecase/${useCaseId}`
      }
    } catch (err) {
      console.error('Error deleting conversation:', err)
      alert('Failed to delete conversation')
    }
  }

  return (
    <>
      {isOpen && <div className="sidebar-overlay" onClick={onClose}></div>}
      <div className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="search-container">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <input
              type="text"
              placeholder="Search conversations..."
              className="search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="sidebar-content">
          <button className="sidebar-menu-item new-conversation-btn" onClick={handleNewConversation}>
            <svg className="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            New Conversation
          </button>

          <button className="sidebar-menu-item" onClick={handleManageDocuments}>
            <svg className="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            Manage Documents
          </button>

          <div className="conversations-section">
            <h3 className="conversations-title">Recent Conversations</h3>
            {loading ? (
              <p className="conversations-loading">Loading...</p>
            ) : conversations.filter(conv => 
                !searchQuery || 
                (conv.title && conv.title.toLowerCase().includes(searchQuery.toLowerCase()))
              ).length > 0 ? (
              <ul className="conversations-list">
                {conversations.filter(conv => 
                  !searchQuery || 
                  (conv.title && conv.title.toLowerCase().includes(searchQuery.toLowerCase()))
                ).map((conv) => (
                  <li
                    key={conv.id}
                    className="conversation-item"
                    onClick={() => handleConversationSelect(conv.id)}
                  >
                    <div className="conversation-info">
                      <div className="conversation-title">{conv.title || 'Untitled Conversation'}</div>
                      <div className="conversation-date">
                        {new Date(conv.updatedAt).toLocaleDateString()}
                      </div>
                    </div>
                    <button
                      className="delete-conversation-btn"
                      onClick={(e) => handleDeleteConversation(e, conv.id)}
                      title="Delete conversation"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="no-conversations">
                {searchQuery ? 'No conversations match your search' : 'No conversations yet'}
              </p>
            )}
          </div>
        </div>
      </div>
      
      <ConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={confirmDelete}
        title="Delete Conversation"
        message="Are you sure you want to delete this conversation? This action cannot be undone."
      />
    </>
  )
}

export default Sidebar
