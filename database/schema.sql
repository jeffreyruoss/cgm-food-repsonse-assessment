-- CGM Food Response Assessment Database Schema
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Glucose Readings Table
CREATE TABLE IF NOT EXISTS glucose_readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    glucose_mg_dl NUMERIC NOT NULL,
    velocity NUMERIC,
    velocity_smoothed NUMERIC,
    is_danger_zone BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp)
);

-- Create index for faster timestamp queries
CREATE INDEX IF NOT EXISTS idx_glucose_timestamp ON glucose_readings(timestamp);

-- Food Logs Table
CREATE TABLE IF NOT EXISTS food_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    food_name TEXT,
    meal_group TEXT,
    calories NUMERIC DEFAULT 0,
    protein_g NUMERIC DEFAULT 0,
    carbs_g NUMERIC DEFAULT 0,
    fat_g NUMERIC DEFAULT 0,
    fiber_g NUMERIC DEFAULT 0,
    sugar_g NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(timestamp, food_name)
);

CREATE INDEX IF NOT EXISTS idx_food_timestamp ON food_logs(timestamp);

-- Imported Files Tracking Table
CREATE TABLE IF NOT EXISTS imported_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT NOT NULL,
    file_mtime NUMERIC NOT NULL,
    file_type TEXT NOT NULL, -- 'glucose' or 'food'
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(file_name, file_mtime)
);

CREATE INDEX IF NOT EXISTS idx_imported_files_name ON imported_files(file_name);

-- Crash Events Table
CREATE TABLE IF NOT EXISTS crash_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    start_glucose NUMERIC,
    end_glucose NUMERIC,
    drop_magnitude NUMERIC,
    average_velocity NUMERIC,
    max_velocity NUMERIC,
    duration_minutes NUMERIC,
    related_food_id UUID REFERENCES food_logs(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(start_time, end_time)
);

CREATE INDEX IF NOT EXISTS idx_crash_start ON crash_events(start_time);

-- Chat History Table (for Gemini memory)
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_history(created_at);

-- User Symptoms Table (for symptom mapping)
CREATE TABLE IF NOT EXISTS user_symptoms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symptom TEXT NOT NULL,
    symptom_time TIMESTAMPTZ NOT NULL,
    severity INTEGER CHECK (severity >= 1 AND severity <= 10),
    notes TEXT,
    analysis TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_symptoms_time ON user_symptoms(symptom_time);

-- Meal AI Assessments Table
CREATE TABLE IF NOT EXISTS meal_ai_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meal_key TEXT NOT NULL UNIQUE,  -- Format: "YYYY-MM-DD_GroupName" for deduplication
    meal_time TIMESTAMPTZ NOT NULL,
    group_name TEXT NOT NULL,
    foods TEXT[],
    carbs_g NUMERIC DEFAULT 0,
    protein_g NUMERIC DEFAULT 0,
    fat_g NUMERIC DEFAULT 0,
    fiber_g NUMERIC DEFAULT 0,
    sugar_g NUMERIC DEFAULT 0,
    baseline_glucose NUMERIC,
    peak_glucose NUMERIC,
    glucose_rise NUMERIC,
    max_drop_velocity NUMERIC,
    total_drop NUMERIC,
    crash_detected BOOLEAN DEFAULT FALSE,
    ai_assessment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meal_assessment_time ON meal_ai_assessments(meal_time);
CREATE INDEX IF NOT EXISTS idx_meal_assessment_key ON meal_ai_assessments(meal_key);

-- Enable Row Level Security (RLS) - optional but recommended
-- Uncomment these if you want to add user authentication later

-- ALTER TABLE glucose_readings ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE food_logs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE crash_events ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_symptoms ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
-- CREATE POLICY "Users can view own data" ON glucose_readings FOR SELECT USING (auth.role() = 'authenticated');
-- CREATE POLICY "Users can insert own data" ON glucose_readings FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- Helpful views

-- View: Daily glucose summary
CREATE OR REPLACE VIEW daily_glucose_summary AS
SELECT
    DATE(timestamp) as date,
    MIN(glucose_mg_dl) as min_glucose,
    MAX(glucose_mg_dl) as max_glucose,
    AVG(glucose_mg_dl) as avg_glucose,
    STDDEV(glucose_mg_dl) as glucose_variability,
    COUNT(*) as reading_count,
    SUM(CASE WHEN glucose_mg_dl < 70 THEN 1 ELSE 0 END) as low_count,
    SUM(CASE WHEN glucose_mg_dl > 140 THEN 1 ELSE 0 END) as high_count,
    SUM(CASE WHEN is_danger_zone THEN 1 ELSE 0 END) as danger_zone_count
FROM glucose_readings
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- View: Daily macro summary
CREATE OR REPLACE VIEW daily_macro_summary AS
SELECT
    DATE(timestamp) as date,
    SUM(calories) as total_calories,
    SUM(protein_g) as total_protein,
    SUM(carbs_g) as total_carbs,
    SUM(fat_g) as total_fat,
    SUM(fiber_g) as total_fiber,
    SUM(sugar_g) as total_sugar,
    COUNT(*) as meal_count
FROM food_logs
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- View: Crash event summary with related food
CREATE OR REPLACE VIEW crash_summary AS
SELECT
    ce.id,
    ce.start_time,
    ce.end_time,
    ce.drop_magnitude,
    ce.max_velocity,
    ce.duration_minutes,
    fl.food_name as potential_trigger,
    fl.carbs_g,
    fl.protein_g,
    fl.sugar_g
FROM crash_events ce
LEFT JOIN food_logs fl ON fl.timestamp BETWEEN (ce.start_time - INTERVAL '3 hours') AND ce.start_time
ORDER BY ce.start_time DESC;
