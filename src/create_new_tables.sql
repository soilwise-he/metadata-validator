-- 1. Add the column to the existing items table
ALTER TABLE harvest.items 
ADD COLUMN IF NOT EXISTS last_validation TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN;

-- 2. Create the history table for detailed logs
CREATE TABLE IF NOT EXISTS harvest.validation_runs (
    run_id SERIAL PRIMARY KEY,
    metadata_identifier TEXT NOT NULL,
    status_passed BOOLEAN NOT NULL,
    validation_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    full_report_json JSONB,
    result_html TEXT
);

-- 3. Create the suite results table
CREATE TABLE IF NOT EXISTS harvest.validation_suite_results (
    result_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES harvest.validation_runs(run_id) ON DELETE CASCADE,
    suite_name TEXT NOT NULL,
    result_status TEXT NOT NULL
);

-- 4. Create indexes for speed
CREATE INDEX IF NOT EXISTS idx_val_run_id ON harvest.validation_runs(metadata_identifier);
CREATE INDEX IF NOT EXISTS idx_val_suite_run ON harvest.validation_suite_results(run_id);