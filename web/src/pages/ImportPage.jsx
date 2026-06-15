import { useRef, useState } from 'react'
import api from '../api/client'

const MAX_FILE_BYTES = 600 * 1024 * 1024

export default function ImportPage() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [scanState, setScanState] = useState('idle') // idle | scanning | indexing | done
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)
  const pollRef = useRef(null)

  function addFiles(fileList) {
    const ACCEPTED = /\.(zip|mp3|m4a|wav|flac)$/i
    const items = Array.from(fileList).map(f => {
      if (!ACCEPTED.test(f.name)) {
        return { file: f, status: 'error', message: 'Unsupported file type. Use .zip, .mp3, .m4a, or .flac.' }
      }
      if (f.size > MAX_FILE_BYTES) {
        return { file: f, status: 'error', message: 'File too large (max 600 MB).' }
      }
      return { file: f, status: 'pending' }
    })
    setFiles(prev => [...prev, ...items])
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    addFiles(e.dataTransfer.files)
  }

  function handleBrowse(e) {
    addFiles(e.target.files)
    e.target.value = ''
  }

  async function handleUpload() {
    const pending = files.filter(f => f.status === 'pending')
    if (!pending.length || uploading) return

    setUploading(true)
    setUploadPct(0)
    setFiles(prev => prev.map(f => f.status === 'pending' ? { ...f, status: 'uploading' } : f))

    const formData = new FormData()
    pending.forEach(item => formData.append('files', item.file))

    try {
      const { data } = await api.post('/import/upload', formData, {
        onUploadProgress: e => {
          if (e.total) setUploadPct(Math.round((e.loaded / e.total) * 100))
        },
      })
      const resultMap = {}
      data.results.forEach(r => { resultMap[r.filename] = r })

      let allOk = true
      setFiles(prev => prev.map(f => {
        if (f.status !== 'uploading') return f
        const r = resultMap[f.file.name]
        if (!r) return { ...f, status: 'error', message: 'No result returned.' }
        if (r.status !== 'ok') allOk = false
        return { ...f, status: r.status, result: r }
      }))

      if (allOk) startScan()
    } catch {
      allOk = false
      setFiles(prev => prev.map(f =>
        f.status === 'uploading' ? { ...f, status: 'error', message: 'Upload failed.' } : f
      ))
    } finally {
      setUploading(false)
      setUploadPct(0)
    }
  }

  function startScan() {
    api.post('/scanner/trigger').then(() => {
      setScanState('scanning')
      pollRef.current = setInterval(() => {
        api.get('/scanner/status').then(r => {
          if (!r.data.running) {
            clearInterval(pollRef.current)
            setScanState('done')
          } else if (r.data.phase === 'indexing') {
            setScanState('indexing')
          }
        })
      }, 2000)
    }).catch(err => {
      if (err.response?.status === 409) setScanState('scanning')
    })
  }

  const pendingCount = files.filter(f => f.status === 'pending').length
  const allDone = files.length > 0 && files.every(f => f.status !== 'pending' && f.status !== 'uploading')
  const anyOk = files.some(f => f.status === 'ok')

  return (
    <div className="page">
      <h2>Import Music</h2>

      <div
        className={`import-dropzone${dragOver ? ' import-dropzone--over' : ''}`}
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => inputRef.current?.click()}
      >
        <div className="import-dropzone-inner">
          <span className="import-dropzone-icon">↓</span>
          <span className="import-dropzone-label">Drop zip files here</span>
          <span className="import-dropzone-sub">or click to browse · Bandcamp, Amazon, and Qobuz zips · loose MP3/M4A/FLAC singles</span>
        </div>
        <input ref={inputRef} type="file" accept=".zip,.mp3,.m4a,.wav,.flac" multiple style={{ display: 'none' }} onChange={handleBrowse} />
      </div>

      {files.length > 0 && (
        <div className="import-file-list">
          {files.map((item, i) => (
            <FileRow key={i} item={item} />
          ))}
        </div>
      )}

      <div className="import-actions">
        {pendingCount > 0 && (
          <button className="btn-primary" onClick={handleUpload} disabled={uploading}>
            {uploading ? `Uploading… ${uploadPct}%` : `Import ${pendingCount} file${pendingCount !== 1 ? 's' : ''}`}
          </button>
        )}
        {uploading && (
          <div className="import-progress-bar">
            <div className="import-progress-fill" style={{ width: `${uploadPct}%` }} />
          </div>
        )}

        {allDone && anyOk && scanState === 'idle' && (
          <button className="btn-primary" onClick={startScan}>Rescan Library</button>
        )}

        {scanState !== 'idle' && (
          <span className={`import-scan-status${scanState === 'done' ? ' import-scan-done' : ''}`}>
            {scanState === 'scanning' && 'Scanning library…'}
            {scanState === 'indexing' && 'Indexing…'}
            {scanState === 'done' && 'Scan complete'}
          </span>
        )}
      </div>
    </div>
  )
}

function FileRow({ item }) {
  const { file, status, result, message } = item
  const icons = { ok: '✓', error: '✗', warning: '⚠', uploading: '…', pending: '' }

  return (
    <div className={`import-file-row import-status-${status}`}>
      <span className="import-file-icon">{icons[status] ?? ''}</span>
      <span className="import-file-name">{file.name}</span>
      <span className="import-file-detail">
        {result?.status === 'ok' && `${result.tracks_imported} track${result.tracks_imported !== 1 ? 's' : ''} → ${result.artist} / ${result.album}`}
        {result?.status === 'error' && result.message}
        {result?.status === 'warning' && result.message}
        {!result && message}
      </span>
    </div>
  )
}
