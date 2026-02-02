import { useState, useEffect, useRef } from 'react'
import './Navbar.css'

function Navbar({ onMenuClick, useCases, selectedUseCase, onUseCaseChange }) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [conversationTitle, setConversationTitle] = useState(null)
  const dropdownRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    const handleTitleUpdate = (event) => {
      setConversationTitle(event.detail.title)
    }

    window.addEventListener('conversationTitleUpdate', handleTitleUpdate)
    return () => window.removeEventListener('conversationTitleUpdate', handleTitleUpdate)
  }, [])

  const handleUseCaseSelect = (useCase) => {
    onUseCaseChange(useCase)
    setIsDropdownOpen(false)
  }

  return (
    <nav className="navbar">
      <button className="hamburger-menu" onClick={onMenuClick}>
        <span></span>
        <span></span>
        <span></span>
      </button>
      <h1 className="navbar-title">Chat App</h1>
      
      {conversationTitle && (
        <div className="conversation-title">{conversationTitle}</div>
      )}
      
      <div className="use-case-dropdown" ref={dropdownRef}>
        <button 
          className="dropdown-button"
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        >
          {selectedUseCase?.name || 'Select Use Case'}
          <span className="dropdown-arrow">{isDropdownOpen ? '▲' : '▼'}</span>
        </button>
        
        {isDropdownOpen && (
          <ul className="dropdown-menu">
            {useCases.map((useCase) => (
              <li
                key={useCase.id}
                className={`dropdown-item ${selectedUseCase?.id === useCase.id ? 'active' : ''}`}
                onClick={() => handleUseCaseSelect(useCase)}
              >
                {useCase.name}
              </li>
            ))}
          </ul>
        )}
      </div>
    </nav>
  )
}

export default Navbar
