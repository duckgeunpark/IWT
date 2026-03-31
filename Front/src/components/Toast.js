import React, { useState, useCallback, useEffect, createContext, useContext } from 'react';
import '../styles/Toast.css';

const ToastContext = createContext(null);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
};

const Toast = ({ id, message, type, onRemove }) => {
  useEffect(() => {
    const timer = setTimeout(() => onRemove(id), 4000);
    return () => clearTimeout(timer);
  }, [id, onRemove]);

  const icons = { success: '\u2705', error: '\u274C', warning: '\u26A0\uFE0F', info: '\u2139\uFE0F' };

  return (
    <div className={`toast toast-${type}`} role="alert">
      <span className="toast-icon">{icons[type] || icons.info}</span>
      <span className="toast-message">{message}</span>
      <button className="toast-close" onClick={() => onRemove(id)}>&times;</button>
    </div>
  );
};

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = {
    success: (msg) => addToast(msg, 'success'),
    error: (msg) => addToast(msg, 'error'),
    warning: (msg) => addToast(msg, 'warning'),
    info: (msg) => addToast(msg, 'info'),
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <Toast key={t.id} {...t} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export default Toast;
