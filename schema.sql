CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    gender VARCHAR(50),
    gender_probability FLOAT,
    sample_size INTEGER,
    age INTEGER,
    age_group VARCHAR(50),
    country_id VARCHAR(10),
    country_probability FLOAT,
    created_at TIMESTAMPTZ NOT NULL
);