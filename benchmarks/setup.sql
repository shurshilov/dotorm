-- Benchmark Database Setup
-- Run this script to create the test database and tables

-- Create database (run as superuser)
-- CREATE DATABASE benchmark_test;

-- Connect to benchmark_test database and run:

-- Drop existing tables
DROP TABLE IF EXISTS benchmark_users CASCADE;
DROP TABLE IF EXISTS benchmark_roles CASCADE;
DROP TABLE IF EXISTS benchmark_article_tags CASCADE;
DROP TABLE IF EXISTS benchmark_articles CASCADE;
DROP TABLE IF EXISTS benchmark_tags CASCADE;

-- Create roles table
CREATE TABLE benchmark_roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255)
);

-- Create users table
CREATE TABLE benchmark_users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    role_id INTEGER REFERENCES benchmark_roles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_benchmark_users_active ON benchmark_users(active);
CREATE INDEX idx_benchmark_users_role_id ON benchmark_users(role_id);
CREATE INDEX idx_benchmark_users_email ON benchmark_users(email);

-- Create tags table (for M2M tests)
CREATE TABLE benchmark_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Create articles table (for M2M tests)
CREATE TABLE benchmark_articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create M2M junction table
CREATE TABLE benchmark_article_tags (
    article_id INTEGER NOT NULL REFERENCES benchmark_articles(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES benchmark_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);

-- Seed some initial data for quick testing
INSERT INTO benchmark_roles (name, description) VALUES
    ('Admin', 'Administrator role'),
    ('User', 'Regular user role'),
    ('Guest', 'Guest role'),
    ('Moderator', 'Moderator role'),
    ('Editor', 'Editor role');

-- Seed users
INSERT INTO benchmark_users (name, email, active, role_id)
SELECT 
    'User ' || i,
    'user' || i || '@benchmark.test',
    (i % 2 = 0),
    (i % 5) + 1
FROM generate_series(1, 10000) AS i;

-- Seed tags
INSERT INTO benchmark_tags (name) VALUES
    ('python'),
    ('database'),
    ('orm'),
    ('async'),
    ('postgresql'),
    ('performance'),
    ('testing'),
    ('benchmark');

-- Seed articles
INSERT INTO benchmark_articles (title, content, published)
SELECT 
    'Article ' || i,
    'Content for article ' || i,
    (i % 3 = 0)
FROM generate_series(1, 1000) AS i;

-- Seed article tags (random associations)
INSERT INTO benchmark_article_tags (article_id, tag_id)
SELECT 
    (i % 1000) + 1,
    (i % 8) + 1
FROM generate_series(1, 5000) AS i
ON CONFLICT DO NOTHING;

-- Show table sizes
SELECT 
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS data_size,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(relid) DESC;
