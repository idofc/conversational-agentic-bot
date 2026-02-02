import { useParams, useSearchParams } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import './UseCase.css'

const API_BASE_URL = 'http://localhost:8000'

function UseCase() {
  const { 'usecase-id': useCaseId, 'conversation-id': conversationId } = useParams()
  const [searchParams] = useSearchParams()
  const isNewConversation = searchParams.get('new') === 'true'
  const [useCaseData, setUseCaseData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [conversationTitle, setConversationTitle] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    // Clear messages and title when switching use cases or conversations
    setMessages([])
    setConversationTitle(null)
    window.dispatchEvent(new CustomEvent('conversationTitleUpdate', { 
      detail: { title: null } 
    }))

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

    const fetchConversation = async () => {
      // Skip loading conversation if this is a new conversation
      if (isNewConversation) {
        return
      }
      
      try {
        let url
        if (conversationId) {
          // Load specific conversation by ID
          url = `${API_BASE_URL}/api/conversations/${conversationId}`
        } else {
          // Load last conversation for this use case
          url = `${API_BASE_URL}/api/use-cases/${useCaseId}/last-conversation`
        }
        
        const response = await fetch(url)
        if (!response.ok) {
          return
        }
        const data = await response.json()
        
        if (data && data.messages && data.messages.length > 0) {
          // Load existing conversation
          const loadedMessages = data.messages.map(msg => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
            conversationId: data.conversationId
          }))
          setMessages(loadedMessages)
          
          // Set conversation title if available
          if (data.title) {
            setConversationTitle(data.title)
            window.dispatchEvent(new CustomEvent('conversationTitleUpdate', { 
              detail: { title: data.title } 
            }))
          }
        }
      } catch (err) {
        console.error('Error fetching conversation:', err)
      }
    }

    fetchUseCaseDetails()
    fetchConversation()
  }, [useCaseId, conversationId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    // Focus input after bot finishes responding
    if (!isSending && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isSending])

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
      
      // Update conversation title if received
      if (data.title) {
        setConversationTitle(data.title)
        // Dispatch custom event to update navbar
        window.dispatchEvent(new CustomEvent('conversationTitleUpdate', { 
          detail: { title: data.title } 
        }))
      }
      
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
                  {new Date(message.timestamp).toLocaleTimeString(undefined, {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })}
                </div>
              </div>
            ))
          )}
          {isSending && (
            <div className="message assistant typing-indicator-container">
              <div className="message-content typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-container" onSubmit={handleSendMessage}>
          <input
            ref={inputRef}
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
