-- Add Meal AI Assessments table for storing AI-generated meal analyses

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
