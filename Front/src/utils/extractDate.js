/**
 * 다양한 날짜 형식의 문자열에서 YYYY-MM-DD 형태의 날짜를 추출
 */
const extractDate = (timeString) => {
  if (!timeString) return null;

  // 한국어 형식: "2023. 08. 13. 오후 03:00:23"
  const koreanDateMatch = timeString.match(/(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\./);
  if (koreanDateMatch) {
    const [, year, month, day] = koreanDateMatch;
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  }

  // "YYYY-MM-DD HH:mm:ss" 형식
  if (timeString.includes('-') && timeString.includes(':')) {
    return timeString.split(' ')[0];
  }

  // "YYYY:MM:DD HH:mm:ss" EXIF 형식
  if (timeString.includes(':')) {
    const parts = timeString.split(' ');
    if (parts[0] && parts[0].split(':').length === 3) {
      return parts[0].replace(/:/g, '-');
    }
  }

  const dateMatch = timeString.match(/(\d{4}[-:]\d{2}[-:]\d{2})/);
  if (dateMatch) {
    return dateMatch[1].replace(/:/g, '-');
  }

  return timeString.split(' ')[0];
};

export default extractDate;
