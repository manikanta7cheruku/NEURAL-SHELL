import { createRoot } from 'react-dom/client'
import '@fontsource/michroma/latin-400.css'
import '@fontsource/jetbrains-mono/latin-400.css'
import '@fontsource/jetbrains-mono/latin-500.css'
import '@fontsource/jetbrains-mono/latin-600.css'
import './index.css'
import App from './App.jsx'
import { applyTheme } from './lib/theme'

applyTheme()            // before the first render, so the saved theme never flashes

createRoot(document.getElementById('root')).render(<App />)
