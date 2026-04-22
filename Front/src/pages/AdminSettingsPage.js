import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import Header from '../components/Header';
import '../styles/AdminSettingsPage.css';

const LABEL_MAP = {
  place_match_radius_m: { label: 'Place 매칭 반경', unit: 'm', min: 5, max: 500, step: 5 },
  cluster_distance_km:  { label: '클러스터 거리 기준', unit: 'km', min: 0.1, max: 5, step: 0.1 },
  cluster_time_hours:   { label: '클러스터 시간 기준', unit: '시간', min: 0.5, max: 24, step: 0.5 },
};

export default function AdminSettingsPage({ toggleTheme, theme }) {
  const { user, isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  const [configs, setConfigs] = useState([]);
  const [editValues, setEditValues] = useState({});
  const [saving, setSaving] = useState({});
  const [error, setError] = useState('');
  const [successKey, setSuccessKey] = useState('');

  const loadSettings = useCallback(async () => {
    try {
      const data = await apiClient.get('/api/v1/admin/settings');
      setConfigs(data);
      const initial = {};
      data.forEach(item => { initial[item.key] = item.value; });
      setEditValues(initial);
    } catch (err) {
      if (err?.status === 403 || err?.response?.status === 403) {
        setError('관리자 권한이 없습니다.');
      } else {
        setError('설정을 불러오는데 실패했습니다.');
      }
    }
  }, []);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/');
      return;
    }
    if (isAuthenticated) {
      loadSettings();
    }
  }, [isAuthenticated, isLoading, navigate, loadSettings]);

  const handleSave = async (key) => {
    setSaving(prev => ({ ...prev, [key]: true }));
    setSuccessKey('');
    try {
      await apiClient.put(`/api/v1/admin/settings/${key}`, { value: String(editValues[key]) });
      setSuccessKey(key);
      setTimeout(() => setSuccessKey(''), 2000);
    } catch (err) {
      setError(`저장 실패: ${err?.detail || err?.message || '알 수 없는 오류'}`);
    } finally {
      setSaving(prev => ({ ...prev, [key]: false }));
    }
  };

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <div className="admin-page">
      <Header toggleTheme={toggleTheme} theme={theme} />
      <div className="admin-container">
        <div className="admin-header">
          <h1>관리자 설정</h1>
          <p className="admin-subtitle">Place 매칭 반경, 클러스터링 기준 등 시스템 파라미터를 조정합니다.</p>
        </div>

        {error && (
          <div className="admin-error">{error}</div>
        )}

        <div className="admin-cards">
          {configs.map(item => {
            const meta = LABEL_MAP[item.key] || { label: item.key, unit: '', min: 0, max: 9999, step: 1 };
            const val = parseFloat(editValues[item.key] ?? item.value);
            const isDirty = String(editValues[item.key]) !== String(item.value);

            return (
              <div key={item.key} className="admin-card">
                <div className="admin-card-header">
                  <span className="admin-card-label">{meta.label}</span>
                  <span className="admin-card-unit">{meta.unit}</span>
                </div>
                <p className="admin-card-desc">{item.description}</p>
                <div className="admin-card-control">
                  <input
                    type="range"
                    min={meta.min}
                    max={meta.max}
                    step={meta.step}
                    value={val}
                    onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
                    className="admin-slider"
                  />
                  <input
                    type="number"
                    min={meta.min}
                    max={meta.max}
                    step={meta.step}
                    value={editValues[item.key] ?? item.value}
                    onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
                    className="admin-number-input"
                  />
                </div>
                <div className="admin-card-footer">
                  <button
                    className={`admin-save-btn ${successKey === item.key ? 'success' : ''}`}
                    onClick={() => handleSave(item.key)}
                    disabled={saving[item.key] || !isDirty}
                  >
                    {saving[item.key] ? '저장 중...' : successKey === item.key ? '저장됨 ✓' : '저장'}
                  </button>
                  {isDirty && <span className="admin-dirty-hint">변경됨</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
