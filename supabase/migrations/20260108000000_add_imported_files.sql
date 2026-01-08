-- Migration: Add imported_files table for tracking auto-imports
-- Date: 2026-01-08

CREATE TABLE IF NOT EXISTS imported_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT NOT NULL,
    file_mtime NUMERIC NOT NULL,
    file_type TEXT NOT NULL, -- 'glucose' or 'food'
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(file_name, file_mtime)
);

CREATE INDEX IF NOT EXISTS idx_imported_files_name ON imported_files(file_name);
