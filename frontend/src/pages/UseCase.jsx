import { useParams } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import './UseCase.css'

const API_BASE_URL = 'http://localhost:8000'

function UseCase() {
  const { 'usecase-id': useCaseId } = useParams()
  const [useCaseData, setUseCaseData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    const fetchUseCaseDetails = async () => {
      try {
        setLoading(true)
        const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}`)
        if (!response.ok) {
          throw new Error('Use case not found')
        }
        const data = await response.json()
        setUseCaseData(data)
      } catch (err) {
        console.error('Error fetching use case details:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchUseCaseDetails()
  }, [useCaseId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSendMessage = async (e) => {
    e.preventDefault()
    
    if (!inputMessage.trim() || isSending) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsSending(true)

    try {
      const response = await fetch(`${API_BASE_URL}/api/use-cases/${useCaseId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          conversationId: messages.length > 0 ? messages[0].conversationId : null
        })
      })

      if (!response.ok) {
        throw new Error('Failed to send message')
      }

      const data = await response.json()
      
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.message,
        timestamp: data.timestamp,
        conversationId: data.conversationId
      }
      
      setMessages(prev => prev.map((msg, idx) => 
        idx === 0 ? { ...msg, conversationId: data.conversationId } : msg
      ).concat([assistantMessage]))
      
    } catch (err) {
      console.error('Error sending message:', err)
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsSending(false)
    }
  }

  if (loading) {
    return (
      <div className="use-case-page">
        <p>Loading...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="use-case-page">
        <h1>Error</h1>
        <p>{error}</p>
      </div>
    )
  }

  return (
    <div className="use-case-page">
      <div className="use-case-header">
        <h1>{useCaseData?.title}</h1>
        <p className="description">{useCaseData?.description}</p>
      </div>

      <div className="chat-container">
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Start a conversation...</p>
              {useCaseData?.details && <p className="details">{useCaseData.details}</p>}
            </div>
          ) : (
            messages.map(message => (
              <div key={message.id} className={`message ${message.role}`}>
                <div 
                  className="message-content"
                  dangerouslySetInnerHTML={{ __html: message.content }}
                />
                <div className="message-timestamp">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-container" onSubmit={handleSendMessage}>
          <input
            type="text"
            className="chat-input"
            placeholder="Type your message..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={isSending}
          />
          <button 
            type="submit" 
            className="send-button"
            disabled={!inputMessage.trim() || isSending}
          >
            {isSending ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default UseCase
