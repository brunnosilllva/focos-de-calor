import React from 'react';
import FocosCalorApp from './components/FocosCalorApp';
import './index.css';

function App() {
  return (
    <div className="App">
      {/* Componente principal do sistema de focos de calor */}
      <FocosCalorApp />
      
      {/* Footer global (opcional) */}
      <div className="sr-only">
        Sistema de monitoramento de focos de calor do Maranhão - IMESC
      </div>
    </div>
  );
}

export default App;
