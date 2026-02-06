-- Migration v13: Code Snippets Module
-- Adds independent code snippets asset library for PR-0128-2026-1

-- Enable foreign keys (required for CASCADE)
PRAGMA foreign_keys = ON;

-- Main snippets table
CREATE TABLE IF NOT EXISTS snippets (
  id TEXT PRIMARY KEY,
  title TEXT,
  language TEXT NOT NULL,
  code TEXT NOT NULL,
  tags_json TEXT,
  source_type TEXT,              -- chat | task | manual
  source_session_id TEXT,
  source_message_id TEXT,
  source_model TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Snippet notes/documentation table
CREATE TABLE IF NOT EXISTS snippet_notes (
  snippet_id TEXT PRIMARY KEY,
  summary TEXT,
  usage TEXT,
  FOREIGN KEY(snippet_id) REFERENCES snippets(id) ON DELETE CASCADE
);

-- FTS5 full-text search table for snippets
CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
  snippet_id UNINDEXED,
  title,
  code,
  tags,
  summary
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_snippets_language ON snippets(language);
CREATE INDEX IF NOT EXISTS idx_snippets_created ON snippets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snippets_source_type ON snippets(source_type);
CREATE INDEX IF NOT EXISTS idx_snippets_source_session ON snippets(source_session_id);

-- Triggers to maintain FTS sync
CREATE TRIGGER IF NOT EXISTS snippets_fts_insert AFTER INSERT ON snippets
BEGIN
  INSERT INTO snippets_fts(snippet_id, title, code, tags, summary)
  VALUES (
    NEW.id,
    COALESCE(NEW.title, ''),
    NEW.code,
    COALESCE(NEW.tags_json, ''),
    COALESCE((SELECT summary FROM snippet_notes WHERE snippet_id = NEW.id), '')
  );
END;

CREATE TRIGGER IF NOT EXISTS snippets_fts_update AFTER UPDATE ON snippets
BEGIN
  DELETE FROM snippets_fts WHERE snippet_id = OLD.id;
  INSERT INTO snippets_fts(snippet_id, title, code, tags, summary)
  VALUES (
    NEW.id,
    COALESCE(NEW.title, ''),
    NEW.code,
    COALESCE(NEW.tags_json, ''),
    COALESCE((SELECT summary FROM snippet_notes WHERE snippet_id = NEW.id), '')
  );
END;

CREATE TRIGGER IF NOT EXISTS snippets_fts_delete AFTER DELETE ON snippets
BEGIN
  DELETE FROM snippets_fts WHERE snippet_id = OLD.id;
END;

-- Trigger to sync snippet_notes INSERT to FTS
CREATE TRIGGER IF NOT EXISTS snippet_notes_fts_insert AFTER INSERT ON snippet_notes
BEGIN
  DELETE FROM snippets_fts WHERE snippet_id = NEW.snippet_id;
  INSERT INTO snippets_fts(snippet_id, title, code, tags, summary)
  SELECT
    s.id,
    COALESCE(s.title, ''),
    s.code,
    COALESCE(s.tags_json, ''),
    COALESCE(NEW.summary, '')
  FROM snippets s
  WHERE s.id = NEW.snippet_id;
END;

-- Trigger to sync snippet_notes UPDATE to FTS
CREATE TRIGGER IF NOT EXISTS snippet_notes_fts_update AFTER UPDATE ON snippet_notes
BEGIN
  DELETE FROM snippets_fts WHERE snippet_id = NEW.snippet_id;
  INSERT INTO snippets_fts(snippet_id, title, code, tags, summary)
  SELECT
    s.id,
    COALESCE(s.title, ''),
    s.code,
    COALESCE(s.tags_json, ''),
    COALESCE(NEW.summary, '')
  FROM snippets s
  WHERE s.id = NEW.snippet_id;
END;

-- Update schema version
INSERT OR REPLACE INTO schema_version (version) VALUES ('0.13.0');
