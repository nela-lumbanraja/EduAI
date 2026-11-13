import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
// Huruf desain disimpan lokal (bukan Google Fonts): Public Sans untuk teks dan judul.
import '@fontsource/public-sans/400.css'
import '@fontsource/public-sans/500.css'
import '@fontsource/public-sans/600.css'
import '@fontsource/public-sans/700.css'
import '@fontsource/public-sans/800.css'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
