import { useState, useEffect } from 'react';

const useTheme = () => {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('iwt-theme') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('iwt-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  return { theme, toggleTheme };
};

export default useTheme;
