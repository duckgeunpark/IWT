/**
 * 배경색의 밝기를 계산하여 적절한 글자색을 반환
 * @param {string} hexColor - 16진수 색상 코드 (예: #ff0000)
 * @returns {string} - 'white' 또는 'black'
 */
const getContrastColor = (hexColor) => {
  const color = hexColor.startsWith('#') ? hexColor.slice(1) : hexColor;

  const r = parseInt(color.substr(0, 2), 16);
  const g = parseInt(color.substr(2, 2), 16);
  const b = parseInt(color.substr(4, 2), 16);

  // YIQ 공식
  const brightness = ((r * 299) + (g * 587) + (b * 114)) / 1000;

  return brightness > 128 ? 'black' : 'white';
};

export default getContrastColor;
