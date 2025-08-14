import React from 'react'
import ReactDOM from 'react-dom/client'
// import App from './App.tsx'  // Original single-model version
import AppMultiModel from './AppMultiModel.tsx'  // Multi-model version
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppMultiModel />
  </React.StrictMode>,
)