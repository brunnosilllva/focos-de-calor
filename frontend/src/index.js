import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// Configuração para produção
if (process.env.NODE_ENV === 'production') {
  console.log('🔥 Focos de Calor - Maranhão | IMESC');
  console.log('📊 Sistema de monitoramento ambiental');
  console.log('🔗 https://github.com/brunnosilllva/focos-de-calor');
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Configuração de Web Vitals para monitoramento de performance
if (process.env.NODE_ENV === 'production') {
  import('./reportWebVitals').then(({ default: reportWebVitals }) => {
    // Enviar métricas para analytics (opcional)
    reportWebVitals((metric) => {
      console.log('📈 Web Vitals:', metric);
      // Aqui você pode enviar para Google Analytics, etc.
    });
  }).catch(() => {
    // Silenciosamente ignorar se reportWebVitals não estiver disponível
  });
}
