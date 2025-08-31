from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # 태그 리스트를 JSON 문자열로 저장 (애플리케이션에서 기본값 '[]' 처리)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recommended_route = Column(Text, nullable=True)  # 추천 경로 정보를 JSON 문자열로 저장
    
    # 관계
    photos = relationship("Photo", back_populates="post", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="post", cascade="all, delete-orphan")

class Photo(Base):
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    file_key = Column(String(500), nullable=False)  # S3 파일 키
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    exif_data = Column(Text, nullable=True)  # EXIF 메타데이터를 JSON 문자열로 저장
    
    # 관계
    post = relationship("Post", back_populates="photos")
    location = relationship("Location", back_populates="photo", uselist=False, cascade="all, delete-orphan")
    labels = relationship("PhotoLabel", back_populates="photo", cascade="all, delete-orphan")

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    landmark = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)  # 위치 추정 신뢰도
    source = Column(String(50), nullable=True)  # 위치 정보 출처 (exif, llm, manual)
    
    # 관계
    photo = relationship("Photo", back_populates="location")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    category_type = Column(String(50), nullable=False)  # country, city, region, theme
    category_name = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=True)  # 카테고리 분류 신뢰도
    
    # 관계
    post = relationship("Post", back_populates="categories")

class RecommendedRoute(Base):
    __tablename__ = "recommended_routes"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    route_name = Column(String(255), nullable=False)
    route_data = Column(Text, nullable=False)  # 전체 경로 데이터를 JSON 문자열로 저장
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    post = relationship("Post")

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(255), primary_key=True, index=True)  # Auth0 user ID
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    picture = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    posts = relationship("Post", backref="user")
    auth_providers = relationship("UserAuthProvider", back_populates="user", cascade="all, delete-orphan")

class UserAuthProvider(Base):
    __tablename__ = "user_auth_providers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=True)
    token = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    user = relationship("User", back_populates="auth_providers")
    
    # 제약조건: 사용자당 프로바이더 하나씩만
    __table_args__ = (
        UniqueConstraint('user_id', 'provider', name='_user_provider_uc'),
    )

# 라벨링 데이터베이스 모델들
class PhotoLabel(Base):
    __tablename__ = "photo_labels"
    
    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    label_type = Column(String(50), nullable=False)  # location, time, camera, image, llm_generated
    label_name = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=True)  # 라벨 신뢰도
    source = Column(String(50), nullable=False)  # 라벨 출처 (exif, llm, manual)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    photo = relationship("Photo", back_populates="labels")

class LLMAnalysis(Base):
    __tablename__ = "llm_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    analysis_type = Column(String(50), nullable=False)  # location, scene, object, sentiment
    analysis_data = Column(Text, nullable=False)  # LLM 분석 결과를 JSON 문자열로 저장
    confidence = Column(Float, nullable=True)  # 분석 신뢰도
    model_used = Column(String(100), nullable=True)  # 사용된 LLM 모델명
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    photo = relationship("Photo")

class ImageMetadata(Base):
    __tablename__ = "image_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    metadata_type = Column(String(50), nullable=False)  # exif, llm_enhanced, manual
    metadata_data = Column(Text, nullable=False)  # 메타데이터를 JSON 문자열로 저장
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계
    photo = relationship("Photo") 