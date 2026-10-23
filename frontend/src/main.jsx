import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { applyTheme } from './lib/theme'

applyTheme()            // before the first render, so the saved theme never flashes

createRoot(document.getElementById('root')).render(<App />)
