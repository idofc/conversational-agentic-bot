import './ConfirmModal.css'

function ConfirmModal({ isOpen, onClose, onConfirm, title, message }) {
  if (!isOpen) return null

  const handleConfirm = () => {
    onConfirm()
    onClose()
  }

  return (
    <>
      <div className="confirm-modal-overlay" onClick={onClose}></div>
      <div className="confirm-modal">
        <div className="confirm-modal-header">
          <h3>{title}</h3>
        </div>
        <div className="confirm-modal-body">
          <p>{message}</p>
        </div>
        <div className="confirm-modal-footer">
          <button className="confirm-modal-btn cancel-btn" onClick={onClose}>
            Cancel
          </button>
          <button className="confirm-modal-btn confirm-btn" onClick={handleConfirm}>
            Delete
          </button>
        </div>
      </div>
    </>
  )
}

export default ConfirmModal
