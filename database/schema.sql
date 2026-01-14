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
    file_mtime BIGINT NOT NULL, -- milliseconds since epoch
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

-- ============================================================================
-- Row Level Security (RLS)
-- ============================================================================
-- RLS is enabled on all tables for security compliance with Supabase best practices.
-- Permissive policies allow full access for single-user app using anon key.
-- For multi-user support, replace these with auth.uid() based policies.

ALTER TABLE glucose_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE crash_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_symptoms ENABLE ROW LEVEL SECURITY;
ALTER TABLE meal_ai_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE imported_files ENABLE ROW LEVEL SECURITY;

-- Single-user permissive policies
CREATE POLICY "Allow all operations on glucose_readings" ON glucose_readings FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on food_logs" ON food_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on crash_events" ON crash_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on chat_history" ON chat_history FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on user_symptoms" ON user_symptoms FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on meal_ai_assessments" ON meal_ai_assessments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all operations on imported_files" ON imported_files FOR ALL USING (true) WITH CHECK (true);
