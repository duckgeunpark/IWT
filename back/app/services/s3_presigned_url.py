"""
S3 Presigned URL 발급 및 관리 서비스
클라이언트에게 안전한 S3 업로드 URL 발급 및 보안 관리
"""

import boto3
import os
from typing import Dict, Optional
from botocore.exceptions import ClientError
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


class S3PresignedURLService:
    """S3 Presigned URL 관리 서비스"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
        )
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        
        # 환경 변수 검증
        if not self.bucket_name:
            logger.error("S3_BUCKET_NAME environment variable is required")
            raise ValueError("S3_BUCKET_NAME environment variable is required")
        
        if not os.getenv('AWS_ACCESS_KEY_ID') or not os.getenv('AWS_SECRET_ACCESS_KEY'):
            logger.error("AWS credentials are required")
            raise ValueError("AWS credentials are required")
        
        logger.info(f"S3 서비스 초기화 완료 - Bucket: {self.bucket_name}, Region: {os.getenv('AWS_REGION', 'ap-northeast-2')}")
    
    async def generate_presigned_url(
        self, 
        file_key: str, 
        content_type: str,
        expiration: int = 3600
    ) -> Dict[str, str]:
        """
        S3 업로드를 위한 presigned URL 생성
        
        Args:
            file_key: S3에 저장될 파일 키
            content_type: 파일의 MIME 타입
            expiration: URL 만료 시간 (초)
            
        Returns:
            presigned URL과 관련 정보를 포함한 딕셔너리
        """
        try:
            logger.info(f"Presigned URL 생성 시작 - file_key: {file_key}, content_type: {content_type}")
            
            # 임시 폴더에 저장
            temp_key = f"temp/{file_key}"
            
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': temp_key,
                    'ContentType': content_type
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Presigned URL 생성 완료 - temp_key: {temp_key}")
            
            return {
                "presigned_url": presigned_url,
                "file_key": temp_key,
                "bucket": self.bucket_name,
                "expires_in": expiration
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Presigned URL 생성 실패 - Code: {error_code}, Message: {error_message}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate upload URL: {error_message}"
            )
        except Exception as e:
            logger.error(f"Presigned URL 생성 중 예상치 못한 오류: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to generate upload URL"
            )
    
    async def move_temp_to_permanent(self, temp_key: str, permanent_key: str) -> bool:
        """
        임시 파일을 영구 저장소로 이동
        
        Args:
            temp_key: 임시 파일 키
            permanent_key: 영구 저장 파일 키
            
        Returns:
            이동 성공 여부
        """
        try:
            logger.info(f"파일 이동 시작 - temp_key: {temp_key}, permanent_key: {permanent_key}")
            
            # 파일 복사
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': temp_key},
                Key=permanent_key
            )
            
            logger.info(f"파일 복사 완료: {temp_key} -> {permanent_key}")
            
            # 임시 파일 삭제
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=temp_key
            )
            
            logger.info(f"임시 파일 삭제 완료: {temp_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"파일 이동 실패 - Code: {error_code}, Message: {error_message}")
            return False
        except Exception as e:
            logger.error(f"파일 이동 중 예상치 못한 오류: {str(e)}")
            return False
    
    async def delete_file(self, file_key: str) -> bool:
        """
        S3에서 파일 삭제
        
        Args:
            file_key: 삭제할 파일 키
            
        Returns:
            삭제 성공 여부
        """
        try:
            logger.info(f"파일 삭제 시작: {file_key}")
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            logger.info(f"파일 삭제 완료: {file_key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"파일 삭제 실패 - Code: {error_code}, Message: {error_message}")
            return False
        except Exception as e:
            logger.error(f"파일 삭제 중 예상치 못한 오류: {str(e)}")
            return False
    
    async def get_file_info(self, file_key: str) -> Optional[Dict]:
        """
        S3 파일 정보 조회
        
        Args:
            file_key: 조회할 파일 키
            
        Returns:
            파일 정보 딕셔너리 또는 None
        """
        try:
            logger.info(f"파일 정보 조회 시작: {file_key}")
            
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            file_info = {
                "size": response.get('ContentLength', 0),
                "content_type": response.get('ContentType', ''),
                "last_modified": response.get('LastModified', ''),
                "etag": response.get('ETag', '')
            }
            
            logger.info(f"파일 정보 조회 완료: {file_info}")
            return file_info
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"파일을 찾을 수 없음: {file_key}")
                return None
            else:
                error_message = e.response['Error']['Message']
                logger.error(f"파일 정보 조회 실패 - Code: {error_code}, Message: {error_message}")
                return None
        except Exception as e:
            logger.error(f"파일 정보 조회 중 예상치 못한 오류: {str(e)}")
            return None
    
    async def check_bucket_access(self) -> bool:
        """
        S3 버킷 접근 권한 확인
        
        Returns:
            접근 가능 여부
        """
        try:
            logger.info(f"S3 버킷 접근 권한 확인: {self.bucket_name}")
            
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            logger.info("S3 버킷 접근 권한 확인 완료")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"S3 버킷 접근 실패 - Code: {error_code}, Message: {error_message}")
            return False
        except Exception as e:
            logger.error(f"S3 버킷 접근 확인 중 예상치 못한 오류: {str(e)}")
            return False


# 싱글톤 인스턴스
s3_service = S3PresignedURLService() 