import React, { useEffect } from 'react';
import { useSettingsStore } from '../store/settingsStore';
import { useUIStore } from '../store/uiStore';

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const loadAllSettings = useSettingsStore((state) => state.loadAllSettings);
  const loaded = useSettingsStore((state) => state.loaded);
  const theme = useSettingsStore((state) => state.theme);
  const uiTheme = useUIStore((state) => state.theme);

  useEffect(() => {
    // Load persisted settings (theme and density) from the database
    loadAllSettings();
  }, [loadAllSettings]);

  useEffect(() => {
    if (loaded && theme !== uiTheme) {
      useUIStore.setState({ theme });
    }
  }, [loaded, theme, uiTheme]);

  if (!loaded) {
    // Return empty or simple loader until settings are loaded
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100vw',
        height: '100vh',
        backgroundColor: '#09090b',
        color: '#fafafa',
        fontFamily: 'sans-serif'
      }}>
        Loading Edeon Settings...
      </div>
    );
  }

  return <>{children}</>;
};
