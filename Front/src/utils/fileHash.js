/**
 * Web Crypto API를 사용하여 파일의 MD5 유사 해시를 계산
 * (SHA-256을 사용하지만 결과를 축약하여 MD5 길이로 반환)
 */
export async function computeFileHash(file) {
  try {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  } catch {
    return null;
  }
}
