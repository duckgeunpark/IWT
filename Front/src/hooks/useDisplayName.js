import { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';

/**
 * DB에 저장된 표시 이름을 우선으로 반환하는 훅
 * 우선순위: DB name → Auth0 nickname → Auth0 name → 이메일 앞부분
 */
const useDisplayName = () => {
  const { user, isAuthenticated } = useAuth0();
  const [dbName, setDbName] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    apiClient.get('/api/v1/users/me')
      .then(data => { if (data?.name) setDbName(data.name); })
      .catch(() => {});
  }, [isAuthenticated]);

  return dbName
    || user?.nickname
    || user?.name
    || user?.email?.split('@')[0]
    || '사용자';
};

export default useDisplayName;
