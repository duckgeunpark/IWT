"""
S3 임시 파일 정리 서비스
temp/ 경로의 만료된 파일을 자동으로 정리한다.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from botocore.exceptions import ClientError

from app.services.s3_presigned_url import S3PresignedURLService

logger = logging.getLogger(__name__)

# 임시 파일 만료 기준 (시간)
TEMP_FILE_EXPIRY_HOURS = 24


class S3CleanupService:
    """S3 임시 파일 정리 서비스"""

    def __init__(self, s3_service: S3PresignedURLService = None):
        if s3_service:
            self.s3_client = s3_service.s3_client
            self.bucket_name = s3_service.bucket_name
        else:
            from app.services.s3_presigned_url import s3_service as default_s3
            self.s3_client = default_s3.s3_client
            self.bucket_name = default_s3.bucket_name

    async def list_temp_files(self, prefix: str = "temp/") -> List[Dict]:
        """temp/ 경로의 파일 목록을 반환한다."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                })

            return files

        except ClientError as e:
            logger.error(f"임시 파일 목록 조회 실패: {e}")
            return []

    async def cleanup_expired_temp_files(
        self, expiry_hours: int = TEMP_FILE_EXPIRY_HOURS
    ) -> Dict:
        """만료된 임시 파일을 삭제한다."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
        temp_files = await self.list_temp_files()

        deleted = []
        failed = []

        for file_info in temp_files:
            last_modified = file_info["last_modified"]
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=timezone.utc)

            if last_modified < cutoff:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=file_info["key"]
                    )
                    deleted.append(file_info["key"])
                    logger.info(f"만료된 임시 파일 삭제: {file_info['key']}")
                except ClientError as e:
                    failed.append(file_info["key"])
                    logger.error(f"임시 파일 삭제 실패: {file_info['key']} - {e}")

        result = {
            "total_scanned": len(temp_files),
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted_keys": deleted,
        }

        logger.info(
            f"임시 파일 정리 완료 - 스캔: {result['total_scanned']}, "
            f"삭제: {result['deleted_count']}, 실패: {result['failed_count']}"
        )

        return result

    async def move_photos_to_permanent(
        self, s3_service: S3PresignedURLService, photo_keys: List[str],
        user_id: str, post_id: int
    ) -> Dict[str, str]:
        """
        임시 경로의 사진들을 영구 경로로 이동한다.
        반환: {temp_key: permanent_key} 매핑
        """
        moved = {}

        for temp_key in photo_keys:
            filename = temp_key.split("/")[-1]
            permanent_key = f"posts/{user_id}/{post_id}/{filename}"

            success = await s3_service.move_temp_to_permanent(
                temp_key=temp_key,
                permanent_key=permanent_key
            )

            if success:
                moved[temp_key] = permanent_key
                logger.info(f"파일 이동 완료: {temp_key} -> {permanent_key}")
            else:
                logger.warning(f"파일 이동 실패: {temp_key}")

        return moved
