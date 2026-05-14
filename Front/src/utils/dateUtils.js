/**
 * 백엔드 날짜 파싱 유틸
 *
 * 백엔드가 UTC 시간을 timezone 표시 없이 반환 ("2024-01-01T15:00:00")
 * → 브라우저가 로컬 시간으로 착각해 9시간 빠르게 표시되는 문제 해결
 * → 'Z'를 붙여 명시적으로 UTC로 인식시킴
 */
const toUTC = (str) => {
  if (!str) return null;
  // 이미 timezone 정보 있으면 그대로 사용
  if (str.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(str)) return new Date(str);
  return new Date(str + 'Z');
};

/** 날짜 문자열 → Date 객체 (UTC 보정) */
export const parseDate = (str) => toUTC(str);

/** "2024. 1. 1." 형식 */
export const formatDate = (str) => {
  const d = toUTC(str);
  return d ? d.toLocaleDateString('ko-KR') : '';
};

/** "2024. 1. 1. 오후 3:00" 형식 */
export const formatDateTime = (str) => {
  const d = toUTC(str);
  return d ? d.toLocaleString('ko-KR') : '';
};

/** "방금 전 / N분 전 / N시간 전 / N일 전 / 날짜" */
export const formatRelativeTime = (str) => {
  const d = toUTC(str);
  if (!d) return '';
  const diff = Date.now() - d.getTime();
  if (diff < 60_000)      return '방금 전';
  if (diff < 3_600_000)   return `${Math.floor(diff / 60_000)}분 전`;
  if (diff < 86_400_000)  return `${Math.floor(diff / 3_600_000)}시간 전`;
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}일 전`;
  return formatDate(str);
};

// ── 사진 촬영 시각 포맷 (게시글 타임존 기준) ─────────────────────────────
//
// 백엔드는 사진별로 두 가지 시각을 보냄:
//   - taken_at_local: naive ISO 문자열 ("2024-03-15T20:00:00") — 게시글 tz 기준 표시값
//   - taken_at_utc: UTC ISO 문자열 — 정렬·산술용
//
// 표시는 taken_at_local 을 그대로 파싱해 보여주는 게 정확함. tz 변환 불필요.
// taken_at_local 이 없으면 taken_at_utc + post.timezone 으로 fallback 변환.

/** naive local ISO + tz → "2024. 3. 15. 오후 8:00" 형식 */
export const formatPhotoTime = (takenAtLocal, takenAtUtc, postTimezone) => {
  if (takenAtLocal) {
    // naive 문자열을 그대로 Date 로 파싱 (브라우저 로컬로 해석되지만 표시만 할 거라 OK)
    const d = new Date(takenAtLocal);
    if (!isNaN(d.getTime())) {
      return d.toLocaleString('ko-KR', {
        year: 'numeric', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
      });
    }
  }
  if (takenAtUtc && postTimezone) {
    const d = toUTC(takenAtUtc);
    if (d) {
      try {
        return d.toLocaleString('ko-KR', {
          timeZone: postTimezone,
          year: 'numeric', month: 'numeric', day: 'numeric',
          hour: 'numeric', minute: '2-digit',
        });
      } catch {
        return d.toLocaleString('ko-KR');
      }
    }
  }
  return '';
};

/** "오후 8:00" 같은 시각만 (날짜 생략) */
export const formatPhotoTimeOnly = (takenAtLocal, takenAtUtc, postTimezone) => {
  if (takenAtLocal) {
    const d = new Date(takenAtLocal);
    if (!isNaN(d.getTime())) {
      return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
    }
  }
  if (takenAtUtc && postTimezone) {
    const d = toUTC(takenAtUtc);
    if (d) {
      try {
        return d.toLocaleTimeString('ko-KR', {
          timeZone: postTimezone, hour: 'numeric', minute: '2-digit',
        });
      } catch {
        return d.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
      }
    }
  }
  return '';
};
