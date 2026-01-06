-- Add meal_group column to food_logs table
ALTER TABLE food_logs ADD COLUMN IF NOT EXISTS meal_group TEXT;
