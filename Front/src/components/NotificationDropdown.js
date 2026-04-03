import React, { useState, useEffect, useRef } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  fetchNotifications,
  fetchUnreadCount,
  markAsRead,
  markAllAsRead,
  deleteNotification,
} from '../store/notificationSlice';
import '../styles/NotificationDropdown.css';

const NOTIFICATION_ICONS = {
  like: '❤️',
  comment: '💬',
  reply: '↩️',
  follow: '👤',
};

const NotificationDropdown = () => {
  const dispatch = useDispatch();
  const { items, unreadCount, loading } = useSelector(state => state.notifications);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // 주기적으로 읽지 않은 알림 수 확인 (60초)
  useEffect(() => {
    dispatch(fetchUnreadCount());
    const interval = setInterval(() => {
      dispatch(fetchUnreadCount());
    }, 60000);
    return () => clearInterval(interval);
  }, [dispatch]);

  // 드롭다운 열릴 때 알림 목록 로드
  useEffect(() => {
    if (isOpen) {
      dispatch(fetchNotifications());
    }
  }, [isOpen, dispatch]);

  // 외부 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNotificationClick = (notif) => {
    if (!notif.is_read) {
      dispatch(markAsRead(notif.id));
    }
  };

  const handleMarkAllRead = () => {
    dispatch(markAllAsRead());
  };

  const handleDelete = (e, notifId) => {
    e.stopPropagation();
    dispatch(deleteNotification(notifId));
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return '방금 전';
    if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  return (
    <div className="notification-dropdown-wrapper" ref={dropdownRef}>
      <button
        className="notification-bell-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="알림"
      >
        🔔
        {unreadCount > 0 && (
          <span className="notification-badge">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-dropdown-header">
            <h4>알림</h4>
            {unreadCount > 0 && (
              <button className="mark-all-read-btn" onClick={handleMarkAllRead}>
                모두 읽음
              </button>
            )}
          </div>

          <div className="notification-list">
            {loading && items.length === 0 && (
              <div className="notification-empty">불러오는 중...</div>
            )}
            {!loading && items.length === 0 && (
              <div className="notification-empty">알림이 없습니다.</div>
            )}
            {items.map((notif) => (
              <div
                key={notif.id}
                className={`notification-item ${notif.is_read ? '' : 'unread'}`}
                onClick={() => handleNotificationClick(notif)}
              >
                <span className="notification-icon">
                  {NOTIFICATION_ICONS[notif.type] || '📢'}
                </span>
                <div className="notification-content">
                  <p className="notification-message">{notif.message}</p>
                  <span className="notification-time">{formatTime(notif.created_at)}</span>
                </div>
                <button
                  className="notification-delete-btn"
                  onClick={(e) => handleDelete(e, notif.id)}
                  title="삭제"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationDropdown;
