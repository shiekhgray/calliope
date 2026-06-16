import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'

const MODES = [
  {
    key: 'classic',
    label: 'Classic',
    desc: 'Follows the trail — each song picks the next most similar one. Adventurous; can roam across genres.',
  },
  {
    key: 'anchor',
    label: 'Anchor',
    desc: 'Keeps circling back to the song you started with, so the station stays in one neighborhood.',
  },
  {
    key: 'ripple',
    label: 'Ripple',
    desc: 'A journey outward — starts right at home and gradually ventures into less similar music.',
  },
  {
    key: 'anchored_ripple',
    label: 'Anchored Ripple',
    desc: 'Stays close to your starting song while always finding something new. The most cohesive option.',
  },
]

const DEFAULTS = { radio_mode: 'classic', radio_variety: 0 }

export default function RadioModesModal({ onClose }) {
  const qc = useQueryClient()

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get('/auth/me').then((r) => r.data),
    staleTime: Infinity,
  })

  const [settings, setSettings] = useState(null)

  useEffect(() => {
    if (me && !settings) {
      setSettings({
        radio_mode: me.radio_mode ?? 'classic',
        radio_variety: me.radio_variety ?? 0,
      })
    }
  }, [me])

  const saveMutation = useMutation({
    mutationFn: (s) => api.put('/auth/radio-settings', s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] })
      onClose()
    },
  })

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal modal--wide" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Radio Modes</h3>
        {!settings ? (
          <p className="loading">Loading…</p>
        ) : (
          <>
            <div className="radio-modes-list">
              {MODES.map(({ key, label, desc }) => (
                <button
                  key={key}
                  type="button"
                  className={`radio-mode-row${settings.radio_mode === key ? ' radio-mode-row--active' : ''}`}
                  onClick={() => setSettings((s) => ({ ...s, radio_mode: key }))}
                >
                  <span className="radio-mode-dot" aria-hidden="true" />
                  <span>
                    <span className="radio-mode-label">{label}</span>
                    <span className="radio-mode-desc">{desc}</span>
                  </span>
                </button>
              ))}
            </div>

            <div className="sim-weights-group">
              <div className="sim-weight-row">
                <div>
                  <div className="sim-weight-label">Variety</div>
                  <div className="sim-weight-desc">Higher = more surprises; lower = always the closest match.</div>
                </div>
                <input
                  type="range"
                  min={0}
                  max={10}
                  step={1}
                  value={settings.radio_variety}
                  onChange={(e) => setSettings((s) => ({ ...s, radio_variety: Number(e.target.value) }))}
                  className="sim-weight-slider"
                />
                <div className="sim-weight-value">{settings.radio_variety}</div>
              </div>
            </div>

            <div className="modal-actions">
              <button className="sim-weights-reset" onClick={() => setSettings({ ...DEFAULTS })} type="button">
                Reset to defaults
              </button>
              <button type="button" onClick={onClose}>Cancel</button>
              <button
                className="btn-primary"
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate(settings)}
              >
                {saveMutation.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
