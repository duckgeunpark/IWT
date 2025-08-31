import React from 'react';
import '../styles/Resizer.css';

const Resizer = ({ onResize, onStart, onEnd, direction = 'horizontal', style }) => {
  const handleMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // 컨테이너 기준 좌표 계산
    const container = document.querySelector('.panels-container');
    const containerRect = container.getBoundingClientRect();
    const startX = e.clientX - containerRect.left;
    const startClientX = e.clientX;
    
    // 드래그 시작 알림
    if (onStart) onStart();
    
    const handleMouseMove = (e) => {
      e.preventDefault();
      const totalDeltaX = e.clientX - startClientX;
      onResize(totalDeltaX);
    };
    
    const handleMouseUp = (e) => {
      e.preventDefault();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
      
      // 드래그 종료 알림 (즉시 처리)
      if (onEnd) {
        requestAnimationFrame(() => onEnd());
      }
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  return (
    <div 
      className={`resizer ${direction}`}
      onMouseDown={handleMouseDown}
      style={style}
    />
  );
};

export default Resizer;