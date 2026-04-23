-- Minimal prerequisite schema that must exist before the bootstrap runs.
-- Mirrors the real harvest schema: only the columns the bootstrap ALTER TABLE touches.
CREATE SCHEMA harvest;

CREATE TABLE harvest.items (
    identifier TEXT PRIMARY KEY,
    resultobject TEXT,
    itemtype TEXT,
    insert_date TIMESTAMP WITH TIME ZONE
);
