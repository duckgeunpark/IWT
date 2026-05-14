/**
 * 큐레이션된 타임존 목록 — 한국 여행자 자주 가는 도시 우선.
 *
 * 각 항목:
 *   - tz: IANA name (예: "Asia/Bangkok")
 *   - offset: GMT 표시용 문자열 (DST 무시한 표준 시각, 검색·UI 표시용)
 *   - label: 한국어 도시명
 *   - country: 한국어 국가명
 *   - flag: 이모지 깃발
 *   - keywords: 검색 키워드 (영문 도시명 포함)
 */

export const TIMEZONES = [
  // ── Asia / Pacific ────────────────────────────────
  { tz: 'Asia/Seoul',       offset: '+9',    label: '서울',        country: '대한민국',     flag: '🇰🇷', keywords: ['seoul', 'korea', '한국', 'kr'] },
  { tz: 'Asia/Tokyo',       offset: '+9',    label: '도쿄·오사카',  country: '일본',         flag: '🇯🇵', keywords: ['tokyo', 'osaka', 'japan', '도쿄', '오사카', '일본'] },
  { tz: 'Asia/Shanghai',    offset: '+8',    label: '베이징·상하이', country: '중국',         flag: '🇨🇳', keywords: ['beijing', 'shanghai', 'china', '베이징', '상하이', '중국'] },
  { tz: 'Asia/Hong_Kong',   offset: '+8',    label: '홍콩',         country: '홍콩',         flag: '🇭🇰', keywords: ['hong kong', 'hongkong', 'hk', '홍콩'] },
  { tz: 'Asia/Taipei',      offset: '+8',    label: '타이베이',     country: '대만',         flag: '🇹🇼', keywords: ['taipei', 'taiwan', '타이베이', '대만'] },
  { tz: 'Asia/Singapore',   offset: '+8',    label: '싱가포르',     country: '싱가포르',     flag: '🇸🇬', keywords: ['singapore', '싱가포르', 'sg'] },
  { tz: 'Asia/Manila',      offset: '+8',    label: '마닐라·세부',  country: '필리핀',       flag: '🇵🇭', keywords: ['manila', 'cebu', 'philippines', '마닐라', '세부', '필리핀'] },
  { tz: 'Asia/Kuala_Lumpur', offset: '+8',   label: '쿠알라룸푸르', country: '말레이시아',   flag: '🇲🇾', keywords: ['kuala lumpur', 'kl', 'malaysia', '쿠알라룸푸르', '말레이시아'] },
  { tz: 'Asia/Bangkok',     offset: '+7',    label: '방콕',         country: '태국',         flag: '🇹🇭', keywords: ['bangkok', 'thailand', '방콕', '태국', 'phuket', '푸켓'] },
  { tz: 'Asia/Ho_Chi_Minh', offset: '+7',    label: '호치민·하노이', country: '베트남',       flag: '🇻🇳', keywords: ['ho chi minh', 'hanoi', 'saigon', 'vietnam', '호치민', '하노이', '베트남', '다낭', 'danang'] },
  { tz: 'Asia/Phnom_Penh',  offset: '+7',    label: '프놈펜',       country: '캄보디아',     flag: '🇰🇭', keywords: ['phnom penh', 'cambodia', 'siem reap', '시엠립', '프놈펜', '캄보디아'] },
  { tz: 'Asia/Vientiane',   offset: '+7',    label: '비엔티안',     country: '라오스',       flag: '🇱🇦', keywords: ['vientiane', 'laos', '비엔티안', '라오스', 'luang prabang'] },
  { tz: 'Asia/Jakarta',     offset: '+7',    label: '자카르타·발리', country: '인도네시아',   flag: '🇮🇩', keywords: ['jakarta', 'bali', 'indonesia', '자카르타', '발리', '인도네시아'] },
  { tz: 'Asia/Yangon',      offset: '+6:30', label: '양곤',         country: '미얀마',       flag: '🇲🇲', keywords: ['yangon', 'myanmar', '양곤', '미얀마'] },
  { tz: 'Asia/Dhaka',       offset: '+6',    label: '다카',         country: '방글라데시',   flag: '🇧🇩', keywords: ['dhaka', 'bangladesh', '다카', '방글라데시'] },
  { tz: 'Asia/Kathmandu',   offset: '+5:45', label: '카트만두',     country: '네팔',         flag: '🇳🇵', keywords: ['kathmandu', 'nepal', '카트만두', '네팔'] },
  { tz: 'Asia/Kolkata',     offset: '+5:30', label: '뉴델리·뭄바이', country: '인도',         flag: '🇮🇳', keywords: ['delhi', 'mumbai', 'india', 'kolkata', '뉴델리', '뭄바이', '인도'] },
  { tz: 'Asia/Karachi',     offset: '+5',    label: '카라치',       country: '파키스탄',     flag: '🇵🇰', keywords: ['karachi', 'pakistan', '카라치', '파키스탄'] },
  { tz: 'Asia/Tashkent',    offset: '+5',    label: '타슈켄트',     country: '우즈베키스탄', flag: '🇺🇿', keywords: ['tashkent', 'uzbekistan', '타슈켄트'] },
  { tz: 'Asia/Dubai',       offset: '+4',    label: '두바이',       country: 'UAE',          flag: '🇦🇪', keywords: ['dubai', 'uae', 'abu dhabi', '두바이', 'emirates'] },
  { tz: 'Australia/Sydney', offset: '+10',   label: '시드니',       country: '호주',         flag: '🇦🇺', keywords: ['sydney', 'melbourne', 'australia', '시드니', '멜버른', '호주'] },
  { tz: 'Pacific/Auckland', offset: '+12',   label: '오클랜드',     country: '뉴질랜드',     flag: '🇳🇿', keywords: ['auckland', 'new zealand', '오클랜드', '뉴질랜드'] },
  { tz: 'Pacific/Guam',     offset: '+10',   label: '괌',           country: '괌',           flag: '🇬🇺', keywords: ['guam', '괌'] },
  { tz: 'Pacific/Honolulu', offset: '-10',   label: '호놀룰루',     country: '하와이',       flag: '🇺🇸', keywords: ['honolulu', 'hawaii', '호놀룰루', '하와이'] },

  // ── Europe ────────────────────────────────────────
  { tz: 'Europe/Istanbul',  offset: '+3',    label: '이스탄불',     country: '튀르키예',     flag: '🇹🇷', keywords: ['istanbul', 'turkey', 'türkiye', '이스탄불', '터키'] },
  { tz: 'Europe/Moscow',    offset: '+3',    label: '모스크바',     country: '러시아',       flag: '🇷🇺', keywords: ['moscow', 'russia', '모스크바', '러시아'] },
  { tz: 'Europe/Athens',    offset: '+2',    label: '아테네',       country: '그리스',       flag: '🇬🇷', keywords: ['athens', 'greece', '아테네', '그리스', 'santorini', '산토리니'] },
  { tz: 'Europe/Helsinki',  offset: '+2',    label: '헬싱키',       country: '핀란드',       flag: '🇫🇮', keywords: ['helsinki', 'finland', '헬싱키', '핀란드'] },
  { tz: 'Europe/Rome',      offset: '+1',    label: '로마·밀라노',  country: '이탈리아',     flag: '🇮🇹', keywords: ['rome', 'milan', 'italy', 'venice', '로마', '밀라노', '베네치아', '이탈리아'] },
  { tz: 'Europe/Berlin',    offset: '+1',    label: '베를린',       country: '독일',         flag: '🇩🇪', keywords: ['berlin', 'munich', 'germany', '베를린', '뮌헨', '독일'] },
  { tz: 'Europe/Paris',     offset: '+1',    label: '파리',         country: '프랑스',       flag: '🇫🇷', keywords: ['paris', 'france', 'nice', '파리', '니스', '프랑스'] },
  { tz: 'Europe/Madrid',    offset: '+1',    label: '마드리드·바르셀로나', country: '스페인', flag: '🇪🇸', keywords: ['madrid', 'barcelona', 'spain', '마드리드', '바르셀로나', '스페인'] },
  { tz: 'Europe/Amsterdam', offset: '+1',    label: '암스테르담',   country: '네덜란드',     flag: '🇳🇱', keywords: ['amsterdam', 'netherlands', '암스테르담', '네덜란드'] },
  { tz: 'Europe/Zurich',    offset: '+1',    label: '취리히',       country: '스위스',       flag: '🇨🇭', keywords: ['zurich', 'switzerland', 'geneva', '취리히', '제네바', '스위스'] },
  { tz: 'Europe/Vienna',    offset: '+1',    label: '빈',           country: '오스트리아',   flag: '🇦🇹', keywords: ['vienna', 'austria', '빈', '오스트리아'] },
  { tz: 'Europe/Prague',    offset: '+1',    label: '프라하',       country: '체코',         flag: '🇨🇿', keywords: ['prague', 'czech', '프라하', '체코'] },
  { tz: 'Europe/London',    offset: '+0',    label: '런던',         country: '영국',         flag: '🇬🇧', keywords: ['london', 'uk', 'britain', '런던', '영국'] },
  { tz: 'Europe/Lisbon',    offset: '+0',    label: '리스본',       country: '포르투갈',     flag: '🇵🇹', keywords: ['lisbon', 'portugal', '리스본', '포르투갈'] },

  // ── Africa / Middle East ──────────────────────────
  { tz: 'Africa/Cairo',     offset: '+2',    label: '카이로',       country: '이집트',       flag: '🇪🇬', keywords: ['cairo', 'egypt', '카이로', '이집트'] },
  { tz: 'Africa/Johannesburg', offset: '+2', label: '요하네스버그', country: '남아공',       flag: '🇿🇦', keywords: ['johannesburg', 'south africa', '요하네스버그', '남아공'] },
  { tz: 'Africa/Casablanca', offset: '+1',   label: '카사블랑카',   country: '모로코',       flag: '🇲🇦', keywords: ['casablanca', 'morocco', '카사블랑카', '모로코', 'marrakech'] },

  // ── Americas ──────────────────────────────────────
  { tz: 'America/Sao_Paulo', offset: '-3',   label: '상파울루',     country: '브라질',       flag: '🇧🇷', keywords: ['sao paulo', 'brazil', '상파울루', '브라질', 'rio'] },
  { tz: 'America/Buenos_Aires', offset: '-3', label: '부에노스아이레스', country: '아르헨티나', flag: '🇦🇷', keywords: ['buenos aires', 'argentina', '부에노스아이레스', '아르헨티나'] },
  { tz: 'America/New_York',  offset: '-5',   label: '뉴욕',         country: '미국 동부',    flag: '🇺🇸', keywords: ['new york', 'nyc', 'boston', 'miami', '뉴욕', '보스턴', '마이애미'] },
  { tz: 'America/Toronto',   offset: '-5',   label: '토론토',       country: '캐나다',       flag: '🇨🇦', keywords: ['toronto', 'canada', '토론토', '캐나다', 'montreal'] },
  { tz: 'America/Mexico_City', offset: '-6', label: '멕시코시티',   country: '멕시코',       flag: '🇲🇽', keywords: ['mexico city', 'mexico', 'cancun', '멕시코', '칸쿤'] },
  { tz: 'America/Chicago',   offset: '-6',   label: '시카고',       country: '미국 중부',    flag: '🇺🇸', keywords: ['chicago', 'dallas', 'houston', '시카고', '댈러스'] },
  { tz: 'America/Denver',    offset: '-7',   label: '덴버',         country: '미국 산악부',  flag: '🇺🇸', keywords: ['denver', '덴버'] },
  { tz: 'America/Los_Angeles', offset: '-8', label: '로스앤젤레스', country: '미국 서부',    flag: '🇺🇸', keywords: ['los angeles', 'la', 'san francisco', 'seattle', '로스앤젤레스', 'la', '샌프란시스코', '시애틀'] },
  { tz: 'America/Vancouver', offset: '-8',   label: '밴쿠버',       country: '캐나다',       flag: '🇨🇦', keywords: ['vancouver', '밴쿠버'] },
];

export const DEFAULT_TIMEZONE = 'Asia/Seoul';

/** IANA name → TIMEZONES 항목 lookup (없으면 fallback synthesized) */
export function findTimezone(tz) {
  if (!tz) return null;
  return TIMEZONES.find(t => t.tz === tz) || null;
}

/** GMT offset 표시용 ("Asia/Bangkok" → "GMT+7") */
export function formatGmtLabel(tz) {
  const entry = findTimezone(tz);
  if (entry) return `GMT${entry.offset}`;
  return tz || 'GMT?';
}

/** 검색 — 키워드 / 도시명 / 국가명 / IANA name 모두 매칭 */
export function searchTimezones(query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return TIMEZONES;
  return TIMEZONES.filter(t => {
    if (t.tz.toLowerCase().includes(q)) return true;
    if (t.label.toLowerCase().includes(q)) return true;
    if (t.country.toLowerCase().includes(q)) return true;
    return t.keywords.some(k => k.toLowerCase().includes(q));
  });
}
