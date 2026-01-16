import React from 'react';
import RiskMap from './RiskMap';

function App() {
  return (
    // We remove default margins to let the map fill the screen
    <div style={{ margin: 0, padding: 0 }}>
      <RiskMap />
    </div>
  );
}

export default App;