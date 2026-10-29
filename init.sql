CREATE TABLE IF NOT EXISTS items (
    id          SERIAL PRIMARY KEY,
    value       TEXT UNIQUE NOT NULL,
    inserted_at TIMESTAMPTZ DEFAULT NOW()
);
