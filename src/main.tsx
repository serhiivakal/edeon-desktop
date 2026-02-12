import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const rootElement = document.getElementById('root') as HTMLElement;

// Fade out and remove the splash screen once the React app is fully mounted and ready
const removeSplashScreen = () => {
  const splash = document.getElementById('splash-screen');
  if (splash) {
    splash.style.opacity = '0';
    setTimeout(() => {
      splash.remove();
    }, 500); // Match transition duration in index.html
  }
};

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Trigger splash screen removal after a short delay to ensure smooth transition
setTimeout(removeSplashScreen, 800);
