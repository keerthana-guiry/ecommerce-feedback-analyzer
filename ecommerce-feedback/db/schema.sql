-- MySQL schema for Ecommerce Feedback Analyzer.
-- Original reviews live in `reviews`. Everything the analysis produces lives in
-- separate tables, so reviews can be re-analyzed without changing the originals.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'analyst') NOT NULL DEFAULT 'analyst',
    default_days SMALLINT UNSIGNED NOT NULL DEFAULT 30,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reviews (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id INT UNSIGNED NOT NULL,
    submitted_by INT UNSIGNED NULL,
    customer_name VARCHAR(100) NULL,
    rating TINYINT UNSIGNED NOT NULL,
    review_text TEXT NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    source ENUM('manual', 'csv') NOT NULL DEFAULT 'manual',
    review_date DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_reviews_product (product_id),
    KEY idx_reviews_date (review_date),
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT fk_reviews_user FOREIGN KEY (submitted_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sentiment_results (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    review_id INT UNSIGNED NOT NULL,
    sentiment ENUM('Positive', 'Neutral', 'Mixed', 'Negative') NOT NULL,
    score DECIMAL(6, 2) NOT NULL,
    confidence DECIMAL(5, 2) NOT NULL,
    emotion VARCHAR(30) NULL,
    spam_score TINYINT UNSIGNED NOT NULL DEFAULT 0,
    model_name VARCHAR(50) NOT NULL,
    analyzed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_sentiment_review (review_id),
    KEY idx_sentiment_label (sentiment),
    CONSTRAINT fk_sentiment_review FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aspect_results (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    review_id INT UNSIGNED NOT NULL,
    aspect VARCHAR(50) NOT NULL,
    sentiment ENUM('Positive', 'Neutral', 'Mixed', 'Negative') NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_aspect_review (review_id, aspect),
    CONSTRAINT fk_aspect_review FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS recommendations (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id INT UNSIGNED NULL,
    complaint_type VARCHAR(100) NOT NULL,
    recommendation TEXT NOT NULL,
    evidence_count INT UNSIGNED NOT NULL DEFAULT 0,
    status ENUM('open', 'done', 'dismissed') NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_recommendations_product (product_id),
    CONSTRAINT fk_recommendations_product FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
