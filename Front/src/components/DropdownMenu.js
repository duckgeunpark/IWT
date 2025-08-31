import React, { useState, useEffect } from 'react';

/**
 * 재사용 가능한 드롭다운 메뉴 컴포넌트
 * @param {Object} props
 * @param {boolean} props.isOpen - 메뉴 열림/닫힘 상태
 * @param {Object} props.position - 메뉴 위치 {top, left}
 * @param {Function} props.onClose - 메뉴 닫기 콜백
 * @param {Array} props.items - 메뉴 아이템 배열
 */
const DropdownMenu = ({ isOpen, position, onClose, items }) => {
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event) => {
      // 드롭다운 메뉴 밖을 클릭했을 때 닫기
      if (!event.target.closest('.dropdown-menu-portal')) {
        onClose();
      }
    };

    // ESC 키로 메뉴 닫기
    const handleEscKey = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleEscKey);

    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleEscKey);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !position) return null;

  return (
    <div 
      className="dropdown-menu-portal"
      style={{
        position: 'fixed',
        top: `${position.top}px`,
        left: `${position.left}px`,
        zIndex: 999999,
        background: 'white',
        border: '1px solid #e0e0e0',
        borderRadius: '8px',
        boxShadow: '0 8px 25px rgba(0, 0, 0, 0.2)',
        minWidth: '80px',
        width: 'auto',
        height: 'auto',
        maxHeight: '200px',
        overflow: 'visible',
        display: 'flex',
        flexDirection: 'column',
        animation: 'fadeInScale 0.15s ease-out'
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {items.map((item, index) => (
        <button
          key={index}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '100%',
            padding: '8px 8px',
            background: 'none',
            border: 'none',
            textAlign: 'left',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            color: item.color || '#374151',
            whiteSpace: 'nowrap',
            minHeight: '32px',
            maxHeight: '32px',
            height: '32px',
            boxSizing: 'border-box',
            borderBottom: index < items.length - 1 ? '1px solid #e5e7eb' : 'none',
            flex: '0 0 auto'
          }}
          onClick={(e) => {
            e.stopPropagation();
            item.onClick();
            onClose(); // 클릭 후 메뉴 닫기
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = item.hoverColor || '#f3f4f6';
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = 'transparent';
          }}
          disabled={item.disabled}
        >
          {item.icon && <span>{item.icon}</span>}
          {item.label}
        </button>
      ))}
    </div>
  );
};

export default DropdownMenu;