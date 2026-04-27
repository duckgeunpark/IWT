import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import AdminLayout from '../components/AdminLayout';
import '../styles/AdminSettingsPage.css';

const LABEL_MAP = {
  place_match_radius_m: { label: 'Place 매칭 반경', unit: 'm', min: 5, max: 500, step: 5 },
  cluster_distance_km:  { label: '클러스터 거리 기준', unit: 'km', min: 0.1, max: 5, step: 0.1 },
  cluster_time_hours:   { label: '클러스터 시간 기준', unit: '시간', min: 0.5, max: 24, step: 0.5 },
  llm_provider:         { label: 'LLM 제공자', unit: '' },
  llm_model_name:       { label: 'LLM 모델명', unit: '' },
};

export default function AdminSettingsPage({ toggleTheme, theme }) {
  const { isAuthenticated, isLoading } = useAuth0();
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
      await apiClient.put(`/api/v1/admin/settings/${key}`, { value: String(editValues[key] ?? '') });
      setSuccessKey(key);
      setTimeout(() => setSuccessKey(''), 2000);
      // 저장 후 최신 값 반영
      await loadSettings();
    } catch (err) {
      setError(`저장 실패: ${err?.detail || err?.message || '알 수 없는 오류'}`);
    } finally {
      setSaving(prev => ({ ...prev, [key]: false }));
    }
  };

  const renderControl = (item) => {
    const meta = LABEL_MAP[item.key] || {};
    const type = item.type || 'string';
    const currentValue = editValues[item.key] ?? item.value;

    if (type === 'number') {
      const min = meta.min ?? 0;
      const max = meta.max ?? 9999;
      const step = meta.step ?? 1;
      const numVal = parseFloat(currentValue);
      return (
        <div className="admin-card-control">
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={isNaN(numVal) ? min : numVal}
            onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
            className="admin-slider"
          />
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={currentValue}
            onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
            className="admin-number-input"
          />
        </div>
      );
    }

    if (type === 'enum') {
      return (
        <div className="admin-card-control">
          <select
            value={currentValue}
            onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
            className="admin-select-input"
          >
            <option value="">(환경변수 사용)</option>
            {(item.options || []).map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      );
    }

    // string
    return (
      <div className="admin-card-control">
        <input
          type="text"
          value={currentValue}
          placeholder="비워두면 환경변수 사용"
          onChange={e => setEditValues(prev => ({ ...prev, [item.key]: e.target.value }))}
          className="admin-text-input"
        />
      </div>
    );
  };

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <AdminLayout
      toggleTheme={toggleTheme}
      theme={theme}
      title="관리자 설정"
      subtitle="시스템 파라미터 및 LLM 설정을 조정합니다."
    >
      {error && <div className="admin-error">{error}</div>}

      <div className="admin-cards">
        {configs.map(item => {
          const meta = LABEL_MAP[item.key] || { label: item.key, unit: '' };
          const isDirty = String(editValues[item.key] ?? '') !== String(item.value);

          return (
            <div key={item.key} className="admin-card">
              <div className="admin-card-header">
                <span className="admin-card-label">{meta.label}</span>
                {meta.unit && <span className="admin-card-unit">{meta.unit}</span>}
              </div>
              <p className="admin-card-desc">{item.description}</p>
              {renderControl(item)}
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
    </AdminLayout>
  );
}
