-- 기존 테이블 삭제 (데이터가 있다면 백업 후)
DROP TABLE IF EXISTS llm_analyses;
DROP TABLE IF EXISTS image_metadata;
DROP TABLE IF EXISTS photo_labels;
DROP TABLE IF EXISTS recommended_routes;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS photos;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS user_auth_providers;
DROP TABLE IF EXISTS users;

-- 사용자 테이블 생성
CREATE TABLE users (
    id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
);

-- 사용자 인증 프로바이더 테이블
CREATE TABLE user_auth_providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(255),
    token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_provider (user_id, provider),
    INDEX idx_user_auth_providers_user_id (user_id),
    INDEX idx_user_auth_providers_provider (provider)
);

-- 포스트 테이블
CREATE TABLE posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    tags TEXT,
    user_id VARCHAR(255) NOT NULL,
    recommended_route TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_posts_user_id (user_id),
    INDEX idx_posts_created_at (created_at)
);

-- 사진 테이블
CREATE TABLE photos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    file_key VARCHAR(500) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    exif_data TEXT,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    INDEX idx_photos_post_id (post_id),
    INDEX idx_photos_upload_time (upload_time)
);

-- 위치 정보 테이블
CREATE TABLE locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    photo_id INT NOT NULL,
    country VARCHAR(100),
    city VARCHAR(100),
    region VARCHAR(100),
    landmark VARCHAR(255),
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    altitude FLOAT,
    confidence FLOAT,
    source VARCHAR(50),
    
    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE,
    INDEX idx_locations_photo_id (photo_id),
    INDEX idx_locations_coordinates (latitude, longitude)
);

-- 카테고리 테이블
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    category_type VARCHAR(50) NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    confidence FLOAT,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    INDEX idx_categories_post_id (post_id),
    INDEX idx_categories_type (category_type)
);

-- 추천 경로 테이블
CREATE TABLE recommended_routes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    route_name VARCHAR(255) NOT NULL,
    route_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    INDEX idx_recommended_routes_post_id (post_id)
);

-- 사진 라벨 테이블
CREATE TABLE photo_labels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    photo_id INT NOT NULL,
    label_type VARCHAR(50) NOT NULL,
    label_name VARCHAR(100) NOT NULL,
    confidence FLOAT,
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE,
    INDEX idx_photo_labels_photo_id (photo_id),
    INDEX idx_photo_labels_type (label_type)
);

-- LLM 분석 테이블
CREATE TABLE llm_analyses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    photo_id INT NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,
    analysis_data TEXT NOT NULL,
    confidence FLOAT,
    model_used VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE,
    INDEX idx_llm_analyses_photo_id (photo_id),
    INDEX idx_llm_analyses_type (analysis_type)
);

-- 이미지 메타데이터 테이블
CREATE TABLE image_metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    photo_id INT NOT NULL,
    metadata_type VARCHAR(50) NOT NULL,
    metadata_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE,
    INDEX idx_image_metadata_photo_id (photo_id),
    INDEX idx_image_metadata_type (metadata_type)
);