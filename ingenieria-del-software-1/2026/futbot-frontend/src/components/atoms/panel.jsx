import './atoms.css'

function Panel({ as: Tag = 'section', className = '', children, ...props }) {
  return (
    <Tag className={`fb-panel ${className}`} {...props}>
      {children}
    </Tag>
  )
}

export default Panel
