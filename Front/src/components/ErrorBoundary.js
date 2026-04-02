import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    if (process.env.NODE_ENV === 'production') {
      // TODO: Sentry 등 에러 리포팅 연동
    }
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          padding: '40px 20px',
          textAlign: 'center',
          color: 'var(--text-primary)',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>!</div>
          <h2 style={{ marginBottom: '8px', fontSize: '20px', fontWeight: 600 }}>
            문제가 발생했습니다
          </h2>
          <p style={{ marginBottom: '24px', color: 'var(--text-secondary)', maxWidth: '400px' }}>
            예기치 않은 오류가 발생했습니다. 다시 시도하거나 페이지를 새로고침해주세요.
          </p>
          {process.env.NODE_ENV !== 'production' && this.state.error && (
            <pre style={{
              marginBottom: '24px',
              padding: '12px 16px',
              background: 'var(--bg-tertiary)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              color: 'var(--danger-color)',
              maxWidth: '500px',
              overflow: 'auto',
              textAlign: 'left',
            }}>
              {this.state.error.toString()}
            </pre>
          )}
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={this.handleRetry} className="btn-primary">
              다시 시도
            </button>
            <button onClick={this.handleReload} className="btn-secondary">
              페이지 새로고침
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
