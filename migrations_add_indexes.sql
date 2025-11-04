CREATE INDEX IF NOT EXISTS ix_queue_enqueued_at ON queue (enqueued_at DESC);
CREATE INDEX IF NOT EXISTS ix_recent_pairs_pair ON recent_pairs (LEAST(user_a,user_b), GREATEST(user_a,user_b));
CREATE INDEX IF NOT EXISTS ix_recent_pairs_time ON recent_pairs (matched_at DESC);
