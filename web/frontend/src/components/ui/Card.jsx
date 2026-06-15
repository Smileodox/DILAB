export default function Card({ children, className = '', hover = false, glow = '', onClick }) {
  return (
    <div
      onClick={onClick}
      className={`
        glass rounded-xl p-5
        ${hover ? 'glass-hover cursor-pointer' : ''}
        ${glow ? `glow-${glow}` : ''}
        ${className}
      `}
    >
      {children}
    </div>
  )
}
