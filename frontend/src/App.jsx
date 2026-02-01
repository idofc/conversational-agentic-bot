import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Sidebar from './components/Sidebar'
import UploadModal from './components/UploadModal'
import Home from './pages/Home'
import UseCase from './pages/UseCase'
import Documents from './pages/Documents'
import './App.css'

const API_BASE_URL = 'http://localhost:8000'

function AppContent() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [useCases, setUseCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    // Fetch use cases from backend
    const fetchUseCases = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/use-cases`)
        if (!response.ok) {
          throw new Error('Failed to fetch use cases')
        }
        const data = await response.json()
        setUseCases(data)
        // Navigate to first use case if on home page
        if (data.length > 0 && location.pathname === '/') {
          navigate(`/usecase/${data[0].uriContext}`)
        }
      } catch (err) {
        console.error('Error fetching use cases:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchUseCases()
  }, [])

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen)
  }

  const handleUseCaseChange = (useCase) => {
    navigate(`/usecase/${useCase.uriContext}`)
    console.log('Selected use case:', useCase)
  }

  const handleUploadClick = () => {
    setIsSidebarOpen(false)
    setIsUploadModalOpen(true)
  }

  // Get current use case from URL
  const pathParts = location.pathname.split('/')
  const currentUriContext = pathParts[2] // Get usecase-id from /usecase/:usecase-id
  const selectedUseCase = useCases.find(uc => uc.uriContext === currentUriContext)

  return (
    <div className="app">
      <Navbar 
        onMenuClick={toggleSidebar}
        useCases={useCases}
        selectedUseCase={selectedUseCase}
        onUseCaseChange={handleUseCaseChange}
      />
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)}
        onUploadClick={handleUploadClick}
      />
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        useCaseUri={currentUriContext}
      />
      <main className="main-content">
        {loading && <p>Loading use cases...</p>}
        {error && <p className="error">Error: {error}</p>}
        {!loading && !error && (
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/usecase/:usecase-id" element={<UseCase />} />
            <Route path="/usecase/:usecase-id/documents" element={<Documents />} />
          </Routes>
        )}
      </main>
    </div>
  )
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  )
}

export default App
