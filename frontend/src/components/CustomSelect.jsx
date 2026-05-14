import { useState, useEffect, useRef } from 'react'

export default function CustomSelect({ icon, value, onChange, options }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const selected = options.find((o) => o.value === value) ?? options[0]

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '7px 10px', background: '#1a1a1a',
          border: '1px solid #262626', borderRadius: 8,
          color: '#cfcfcf', fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap',
        }}
      >
        {icon && <span style={{ color: '#5a5a5a', display: 'flex' }}>{icon}</span>}
        <span>{selected?.label}</span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          style={{ color: '#5a5a5a', transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0,
          background: '#1a1a1a', border: '1px solid #262626', borderRadius: 8,
          overflow: 'hidden', zIndex: 50, minWidth: '100%',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
        }}>
          {options.map((o) => (
            <div
              key={o.value}
              onClick={() => { onChange(o.value); setOpen(false) }}
              style={{
                padding: '8px 14px', fontSize: 12, cursor: 'pointer',
                color: o.value === value ? '#fff' : '#9a9a9a',
                background: o.value === value ? 'rgba(255,255,255,0.06)' : 'transparent',
                transition: 'background 0.1s',
              }}
            >
              {o.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
