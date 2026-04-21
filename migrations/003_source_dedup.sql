-- Migration: 003_source_dedup
-- Adds source-based deduplication for document ingestion pipelines

-- Add source_hash for tracking original document identity
-- Add chunk_index for tracking position within chunked documents
ALTER TABLE memories
ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64),
ADD COLUMN IF NOT EXISTS chunk_index INTEGER;

-- Index for source-based deduplication queries
CREATE INDEX IF NOT EXISTS idx_memories_source_hash
    ON memories (source_hash)
    WHERE source_hash IS NOT NULL;

-- Composite unique constraint for source-based upserts
-- Same source document + same chunk position = same memory
CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_source_chunk
    ON memories (namespace, source_hash, chunk_index)
    WHERE source_hash IS NOT NULL;

-- Index for finding all chunks of a source document
CREATE INDEX IF NOT EXISTS idx_memories_source_chunk_lookup
    ON memories (namespace, source_hash, chunk_index)
    WHERE source_hash IS NOT NULL;

COMMENT ON COLUMN memories.source_hash IS 'Hash of original source document (for pipeline dedup)';
COMMENT ON COLUMN memories.chunk_index IS 'Position within chunked source document';
