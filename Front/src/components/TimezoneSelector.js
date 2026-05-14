import React, { useState, useRef, useEffect, useMemo } from 'react';
import { TIMEZONES, findTimezone, searchTimezones } from '../data/timezones';
import '../styles/TimezoneSelector.css';

/**
 * 타임존 선택 칩 + 드롭다운.
 *
 * Props:
 *   - value: 현재 선택된 IANA tz name (예: "Asia/Bangkok")
 *   - onChange: (newTz: string) => void
 *   - detectedTz: 자동 감지된 IANA tz (강조 표시용, 옵션)
 *   - compact: true 면 작은 크기 (편집 페이지용)
 */
const TimezoneSelector = ({ value, onChange, detectedTz, compact = false }) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef(null);

  const current = useMemo(() => findTimezone(value) || findTimezone(detectedTz), [value, detectedTz]);

  const results = useMemo(() => searchTimezones(query), [query]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const handlePick = (tz) => {
    onChange?.(tz);
    setOpen(false);
    setQuery('');
  };

  const chipLabel = current
    ? `${current.flag} GMT${current.offset} · ${current.label}`
    : (value ? `GMT? · ${value}` : '타임존 선택');

  return (
    <div className={`tz-selector${compact ? ' compact' : ''}`} ref={ref}>
      <button
        type="button"
        className="tz-chip"
        onClick={() => setOpen(o => !o)}
        title={value || ''}
      >
        <span className="tz-chip-label">{chipLabel}</span>
        <span className="tz-chip-arrow">▾</span>
      </button>

      {open && (
        <div className="tz-dropdown" role="listbox">
          <div className="tz-search">
            <input
              type="text"
              className="tz-search-input"
              placeholder="국가·도시 검색 (예: 방콕, tokyo)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <ul className="tz-options">
            {results.length === 0 ? (
              <li className="tz-empty">검색 결과 없음</li>
            ) : (
              results.map(t => {
                const isSelected = t.tz === value;
                const isDetected = t.tz === detectedTz;
                return (
                  <li
                    key={t.tz}
                    className={`tz-option${isSelected ? ' selected' : ''}`}
                    onClick={() => handlePick(t.tz)}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <span className="tz-option-flag">{t.flag}</span>
                    <span className="tz-option-offset">GMT{t.offset}</span>
                    <span className="tz-option-label">{t.label}</span>
                    <span className="tz-option-country">{t.country}</span>
                    {isDetected && <span className="tz-option-badge">감지됨</span>}
                    {isSelected && <span className="tz-option-check">✓</span>}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      )}
    </div>
  );
};

export default TimezoneSelector;
