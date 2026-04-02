/**
 * 클라이언트 측 이미지 압축 유틸리티
 * canvas API를 사용하여 외부 라이브러리 없이 구현
 */

const DEFAULT_OPTIONS = {
  maxWidth: 2048,
  maxHeight: 2048,
  quality: 0.85,
  maxSizeMB: 2,
};

/**
 * 이미지를 로드하여 HTMLImageElement를 반환한다.
 */
const loadImage = (file) =>
  new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    const url = URL.createObjectURL(file);
    img.src = url;
  });

/**
 * 이미지 파일을 압축하여 새로운 File 객체를 반환한다.
 * EXIF 데이터는 별도로 추출되므로 압축된 이미지에는 포함되지 않는다.
 */
export const compressImage = async (file, options = {}) => {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  // 이미 충분히 작으면 그대로 반환
  if (file.size <= opts.maxSizeMB * 1024 * 1024) {
    return file;
  }

  // GIF/WebP 등 투명도가 필요한 포맷은 압축하지 않음
  if (file.type === 'image/gif') {
    return file;
  }

  try {
    const img = await loadImage(file);

    let { width, height } = img;

    // 비율 유지하며 리사이즈
    if (width > opts.maxWidth || height > opts.maxHeight) {
      const ratio = Math.min(opts.maxWidth / width, opts.maxHeight / height);
      width = Math.round(width * ratio);
      height = Math.round(height * ratio);
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, width, height);

    // ObjectURL 정리
    URL.revokeObjectURL(img.src);

    const outputType = file.type === 'image/png' ? 'image/png' : 'image/jpeg';

    const blob = await new Promise((resolve) => {
      canvas.toBlob(resolve, outputType, opts.quality);
    });

    if (!blob) return file;

    return new File([blob], file.name, {
      type: outputType,
      lastModified: file.lastModified,
    });
  } catch {
    // 압축 실패 시 원본 반환
    return file;
  }
};

/**
 * 썸네일을 생성하여 Blob URL을 반환한다.
 */
export const createThumbnail = async (file, size = 300) => {
  try {
    const img = await loadImage(file);

    const ratio = Math.min(size / img.width, size / img.height);
    const width = Math.round(img.width * ratio);
    const height = Math.round(img.height * ratio);

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, width, height);

    URL.revokeObjectURL(img.src);

    const blob = await new Promise((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', 0.7);
    });

    return blob ? URL.createObjectURL(blob) : URL.createObjectURL(file);
  } catch {
    return URL.createObjectURL(file);
  }
};
