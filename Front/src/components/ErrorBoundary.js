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
    // 프로덕션에서는 에러 리포팅 서비스로 전송
    if (process.env.NODE_ENV === 'production') {
      // TODO: Sentry 등 에러 리포팅 연동
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px',
          textAlign: 'center',
        }}>
          <h2 style={{ marginBottom: '12px', color: '#333' }}>
            문제가 발생했습니다
          </h2>
          <p style={{ marginBottom: '20px', color: '#666' }}>
            페이지를 새로고침하거나 다시 시도해주세요.
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '8px 20px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            다시 시도
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
