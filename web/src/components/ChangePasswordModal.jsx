import { useRef, useState } from 'react'
import api from '../api/client'

export default function ChangePasswordModal({ onClose }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (next !== confirm) { setError('New passwords do not match'); return }
    setLoading(true)
    try {
      await api.post('/auth/change-password', { current_password: current, new_password: next })
      setDone(true)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Change password</h3>
        {done ? (
          <>
            <p className="modal-success">Password updated.</p>
            <div className="modal-actions">
              <button className="btn-primary" onClick={onClose}>Done</button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <label>Current password
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus required />
            </label>
            <label>New password
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required />
            </label>
            <label>Confirm new password
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </label>
            {error && <p className="error">{error}</p>}
            <div className="modal-actions">
              <button type="button" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Saving…' : 'Update password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
