CREATE TABLE IF NOT EXISTS queue (
  user_id     BIGINT PRIMARY KEY,
  sex         TEXT,
  age         INT,
  lang        TEXT,
  interests   TEXT,
  vibe        TEXT,
  adult_ok    BOOLEAN DEFAULT FALSE,
  is_premium  BOOLEAN DEFAULT FALSE,
  enqueued_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_queue_enqueued ON queue(enqueued_at);
CREATE INDEX IF NOT EXISTS idx_queue_premium ON queue(is_premium);
CREATE INDEX IF NOT EXISTS idx_queue_sex ON queue(sex);
CREATE INDEX IF NOT EXISTS idx_queue_lang ON queue(lang);
CREATE INDEX IF NOT EXISTS idx_queue_age ON queue(age);

CREATE TABLE IF NOT EXISTS pairs (
  a_id       BIGINT NOT NULL,
  b_id       BIGINT NOT NULL,
  started_at BIGINT NOT NULL,
  ended_at   BIGINT,
  PRIMARY KEY (a_id, b_id, started_at)
);
CREATE INDEX IF NOT EXISTS idx_pairs_a ON pairs(a_id);
CREATE INDEX IF NOT EXISTS idx_pairs_b ON pairs(b_id);

CREATE TABLE IF NOT EXISTS recent_pairs (
  a_id       BIGINT NOT NULL,
  b_id       BIGINT NOT NULL,
  matched_at BIGINT NOT NULL,
  PRIMARY KEY (a_id, b_id)
);
CREATE INDEX IF NOT EXISTS idx_recent_a ON recent_pairs(a_id);
CREATE INDEX IF NOT EXISTS idx_recent_b ON recent_pairs(b_id);
