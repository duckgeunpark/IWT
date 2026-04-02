/**
 * Redux 외부 File 객체 저장소
 * File/Blob은 직렬화 불가능하므로 Redux store 밖에서 관리한다.
 */
const fileMap = new Map();

export const fileStore = {
  set(photoId, file) {
    fileMap.set(photoId, file);
  },

  get(photoId) {
    return fileMap.get(photoId) || null;
  },

  delete(photoId) {
    fileMap.delete(photoId);
  },

  clear() {
    fileMap.clear();
  },

  has(photoId) {
    return fileMap.has(photoId);
  },
};

export default fileStore;
