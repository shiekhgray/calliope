import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'

const GROUPS = [
  {
    label: 'Timbre',
    rows: [
      { key: 'timbre',            label: 'Tone Color',        desc: 'How the instruments sound' },
      { key: 'timbral_variation', label: 'Timbral Variation', desc: 'How much the texture changes' },
      { key: 'brightness',        label: 'Brightness',        desc: 'Bass-heavy vs treble-heavy' },
    ],
  },
  {
    label: 'Harmony',
    rows: [
      { key: 'harmony',        label: 'Harmonic Content', desc: 'What notes/chords are present' },
      { key: 'chord_movement', label: 'Chord Movement',   desc: 'How fast the harmony changes' },
      { key: 'tonal',          label: 'Tonal Character',  desc: 'Key, mode, and chord relationships' },
    ],
  },
  {
    label: 'Rhythm & Energy',
    rows: [
      { key: 'tempo',          label: 'Tempo',         desc: 'Pace of the music (BPM)' },
      { key: 'loudness',       label: 'Loudness',      desc: 'Average volume level' },
      { key: 'dynamic_range',  label: 'Dynamic Range', desc: 'How much the volume varies' },
    ],
  },
]

const DEFAULTS = {
  timbre: 5, timbral_variation: 5, harmony: 5,
  chord_movement: 5, tempo: 5, loudness: 5,
  dynamic_range: 5, brightness: 5, tonal: 5,
}

export default function SimilarityWeightsModal({ onClose }) {
  const qc = useQueryClient()
  const { currentTrack } = usePlayer()

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get('/auth/me').then((r) => r.data),
    staleTime: Infinity,
  })

  const [weights, setWeights] = useState(null)

  useEffect(() => {
    if (me && !weights) {
      setWeights({
        timbre:            me.sim_weight_timbre,
        timbral_variation: me.sim_weight_timbral_variation,
        harmony:           me.sim_weight_harmony,
        chord_movement:    me.sim_weight_chord_movement,
        tempo:             me.sim_weight_tempo,
        loudness:          me.sim_weight_loudness,
        dynamic_range:     me.sim_weight_dynamic_range,
        brightness:        me.sim_weight_brightness,
        tonal:             me.sim_weight_tonal,
      })
    }
  }, [me])

  const saveMutation = useMutation({
    mutationFn: (w) => api.put('/auth/similarity-weights', w),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] })
      if (currentTrack) qc.invalidateQueries({ queryKey: ['similar', currentTrack.id] })
      onClose()
    },
  })

  function setWeight(key, value) {
    setWeights((prev) => ({ ...prev, [key]: value }))
  }

  function resetDefaults() {
    setWeights({ ...DEFAULTS })
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal modal--wide" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Sound Matching</h3>
        {!weights ? (
          <p className="loading">Loading…</p>
        ) : (
          <>
            {GROUPS.map((group) => (
              <div key={group.label} className="sim-weights-group">
                <div className="sim-weights-group-label">{group.label}</div>
                {group.rows.map(({ key, label, desc }) => (
                  <div key={key} className="sim-weight-row">
                    <div>
                      <div className="sim-weight-label">{label}</div>
                      <div className="sim-weight-desc">{desc}</div>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={10}
                      step={1}
                      value={weights[key]}
                      onChange={(e) => setWeight(key, Number(e.target.value))}
                      className="sim-weight-slider"
                    />
                    <div className="sim-weight-value">{weights[key]}</div>
                  </div>
                ))}
              </div>
            ))}
            <div className="modal-actions">
              <button className="sim-weights-reset" onClick={resetDefaults} type="button">
                Reset to defaults
              </button>
              <button type="button" onClick={onClose}>Cancel</button>
              <button
                className="btn-primary"
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate(weights)}
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
