from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
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
    status = Column(String(50), nullable=False, default='published', server_default='published')
    user_id = Column(String(255), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recommended_route = Column(Text, nullable=True)  # 추천 경로 정보를 JSON 문자열로 저장
    blocks         = Column(LONGTEXT, nullable=True)        # JSON blocks[] — 레거시 (blocks_mode='legacy')
    blocks_version = Column(Integer, default=0)           # 재생성 이력 추적용 버전 번호
    has_user_edits = Column(Boolean, default=False)       # 사용자 편집 여부 플래그
    blocks_mode    = Column(String(20), default='legacy', server_default='legacy')
    # 'legacy': posts.blocks JSON 사용 (기존 게시글)
    # 'v2':     post_blocks 테이블 사용 (신규 게시글)
    deleted_at     = Column(DateTime, nullable=True, index=True)  # 관리자 soft delete 마커. NOT NULL이면 일반 조회에서 제외

    # 관계
    photos = relationship("Photo", back_populates="post", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    bookmarks = relationship("PostBookmark", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    clusters = relationship("Cluster", back_populates="post", cascade="all, delete-orphan")
    post_blocks = relationship("PostBlock", back_populates="post", cascade="all, delete-orphan",
                               order_by="PostBlock.block_order")

class Cluster(Base):
    """사진 클러스터 — GPS centroid + 날짜 기반 stable identity"""
    __tablename__ = "clusters"

    id            = Column(Integer, primary_key=True, index=True)
    post_id       = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_hash  = Column(String(64), nullable=False, index=True)  # GPS grid + date hash (안정적 identity)
    centroid_lat  = Column(Float, nullable=True)
    centroid_lng  = Column(Float, nullable=True)
    location_name = Column(String(255), nullable=True)
    city          = Column(String(100), nullable=True)
    country       = Column(String(100), nullable=True)
    time_start    = Column(DateTime, nullable=True)
    time_end      = Column(DateTime, nullable=True)
    photo_count   = Column(Integer, default=0)
    cluster_order = Column(Integer, default=0)
    ai_paragraph  = Column(Text, nullable=True)  # 레거시 Stage 2 단락 캐시
    place_note    = Column(LONGTEXT, nullable=True)  # v2 PlaceNote JSON 캐시 (fingerprint 기반 재사용)

    post = relationship("Post", back_populates="clusters")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    cluster_id = Column(Integer, ForeignKey("clusters.id"), nullable=True, index=True)
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

class PostLike(Base):
    __tablename__ = "post_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="likes")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='_post_user_like_uc'),
    )

class PostBookmark(Base):
    __tablename__ = "post_bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("Post", back_populates="bookmarks")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='_post_user_bookmark_uc'),
    )

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("Post", back_populates="comments")
    user = relationship("User")
    replies = relationship("Comment", backref="parent", remote_side=[id], cascade="all, delete-orphan", single_parent=True)

class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    follower = relationship("User", foreign_keys=[follower_id], backref="following_relations")
    following = relationship("User", foreign_keys=[following_id], backref="follower_relations")

    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', name='_follower_following_uc'),
    )

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # like, comment, follow, reply
    message = Column(Text, nullable=False)
    actor_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_id])


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


# ═══════════════════════════════════════════
# 데이터 정규화 테이블 (AI 학습용)
# ═══════════════════════════════════════════

class Place(Base):
    """장소 마스터 테이블 - 재사용 가능한 장소 정보"""
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    place_type = Column(String(100), nullable=True)  # restaurant, cafe, tourist_attraction, park, etc.
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    avg_stay_duration = Column(Integer, nullable=True)  # 평균 체류 시간 (초)
    visit_count = Column(Integer, default=0)  # 방문 횟수 (통계용)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    route_stops = relationship("RouteStop", back_populates="place")


class Route(Base):
    """경로 정보 - 하나의 여행(Post)에 하나의 경로"""
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    total_distance = Column(Float, nullable=True)  # 총 이동 거리 (미터)
    total_duration = Column(Integer, nullable=True)  # 총 이동 시간 (초)
    total_stops = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    post = relationship("Post", backref="routes")
    stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.stop_order")
    segments = relationship("RouteSegment", back_populates="route", cascade="all, delete-orphan", order_by="RouteSegment.segment_order")


class RouteStop(Base):
    """경유지 - 경로 내 방문 장소"""
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), nullable=True)
    stop_order = Column(Integer, nullable=False)  # 방문 순서
    arrival_time = Column(DateTime, nullable=True)
    departure_time = Column(DateTime, nullable=True)
    stay_duration = Column(Integer, nullable=True)  # 체류 시간 (초)
    stay_duration_source = Column(String(50), nullable=True)  # estimated, photo_based, user_input
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    name = Column(String(255), nullable=True)  # Place가 없을 때 사용
    day_number = Column(Integer, nullable=True)  # N일차
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    route = relationship("Route", back_populates="stops")
    place = relationship("Place", back_populates="route_stops")
    photos = relationship("Photo", secondary="route_stop_photos")


# 경유지-사진 다대다 관계 테이블
from sqlalchemy import Table
route_stop_photos = Table(
    "route_stop_photos",
    Base.metadata,
    Column("route_stop_id", Integer, ForeignKey("route_stops.id", ondelete="CASCADE"), primary_key=True),
    Column("photo_id", Integer, ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True),
)


class RouteSegment(Base):
    """이동 구간 - 두 경유지 사이의 이동 정보"""
    __tablename__ = "route_segments"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_order = Column(Integer, nullable=False)  # 구간 순서
    from_stop_id = Column(Integer, ForeignKey("route_stops.id", ondelete="CASCADE"), nullable=False)
    to_stop_id = Column(Integer, ForeignKey("route_stops.id", ondelete="CASCADE"), nullable=False)
    transport_mode = Column(String(50), nullable=True)  # driving, walking, bicycling, transit
    transport_mode_source = Column(String(50), nullable=True)  # estimated, google_api, user_input
    distance = Column(Float, nullable=True)  # 이동 거리 (미터)
    duration = Column(Integer, nullable=True)  # 이동 시간 (초)
    polyline = Column(Text, nullable=True)  # 인코딩된 경로 폴리라인
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    route = relationship("Route", back_populates="segments")
    from_stop = relationship("RouteStop", foreign_keys=[from_stop_id])
    to_stop = relationship("RouteStop", foreign_keys=[to_stop_id])


class UserLLMPreference(Base):
    """사용자별 LLM 파이프라인 커스터마이즈 설정"""
    __tablename__ = "user_llm_preferences"

    user_id      = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tone         = Column(String(50),  nullable=False, default="casual")   # casual|formal|poetic|humorous
    style        = Column(String(50),  nullable=False, default="blog")     # blog|diary|travel_guide
    lang         = Column(String(10),  nullable=False, default="ko")       # ko|en|ja|zh|fr
    stage1_extra = Column(Text, nullable=True)   # Stage1 추가 지침
    stage2_extra = Column(Text, nullable=True)   # Stage2 추가 지침
    stage3_extra = Column(Text, nullable=True)   # Stage3 추가 지침
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class SystemConfig(Base):
    """관리자 조정 가능한 시스템 설정 (키-값)"""
    __tablename__ = "system_configs"

    key         = Column(String(100), primary_key=True)
    value       = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserCorrection(Base):
    """사용자 수정 이력 - AI 학습 라벨용"""
    __tablename__ = "user_corrections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # route_stop, route_segment, place
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String(100), nullable=False)  # transport_mode, stay_duration, name, etc.
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=False)
    correction_source = Column(String(50), default="user_input")  # user_input, suggested
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# ═══════════════════════════════════════════
# v2 블록 기반 게시글 시스템
# ═══════════════════════════════════════════

class PostBlock(Base):
    """
    게시글 블록 — v2 생성 시스템에서 사용.
    posts.blocks_mode = 'v2' 인 게시글은 이 테이블에서 블록을 읽는다.

    블록 타입:
      title       — 게시글 제목 (1개)
      intro       — 여행 전체 도입부 (1개)
      day_header  — n일차 헤더 (지도 핀 JSON + 타임라인 데이터, LLM 없음)
      place       — 장소 블록 (시간순, depth=main|brief)
      day_outro   — 일차 마무리 (선택)
      tags        — 태그 목록 (1개)
    """
    __tablename__ = "post_blocks"

    id          = Column(Integer, primary_key=True, index=True)
    post_id     = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    block_type  = Column(String(30), nullable=False)
    block_order = Column(Integer, nullable=False)
    day         = Column(Integer, nullable=True)
    cluster_id  = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    pin_number  = Column(Integer, nullable=True)

    # 타임라인 정보 (place 블록만)
    stay_min              = Column(Integer, nullable=True)
    travel_from_prev_min  = Column(Integer, nullable=True)
    distance_from_prev_km = Column(Float, nullable=True)
    transport             = Column(String(20), nullable=True)

    # 콘텐츠
    depth         = Column(String(10), default='brief')
    ai_content    = Column(LONGTEXT, nullable=True)
    user_content  = Column(LONGTEXT, nullable=True)
    locked        = Column(Boolean, default=False)
    quality_score = Column(Float, nullable=True)

    version    = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    post    = relationship("Post", back_populates="post_blocks")
    cluster = relationship("Cluster")