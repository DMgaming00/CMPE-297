-- PostgreSQL schema for Agent C's production bug tracker (behind MCP Toolbox).
-- Mirrors agents/bug_assistant/mcp_server/store.py (SQLite, local development).

CREATE TABLE IF NOT EXISTS tickets (
  id            BIGSERIAL PRIMARY KEY,
  title         TEXT NOT NULL CHECK (char_length(title) BETWEEN 8 AND 160),
  description   TEXT NOT NULL CHECK (char_length(description) BETWEEN 20 AND 5000),
  status        TEXT NOT NULL CHECK (status IN ('open','in_progress','resolved','closed',
                                                'duplicate')),
  priority      TEXT NOT NULL CHECK (priority IN ('P0','P1','P2','P3')),
  component     TEXT NOT NULL CHECK (component ~ '^[a-z0-9][a-z0-9._-]{1,39}$'),
  reporter      TEXT NOT NULL,
  assignee      TEXT NOT NULL DEFAULT '',
  duplicate_of  BIGINT REFERENCES tickets(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  search_vector TSVECTOR GENERATED ALWAYS AS (
    setweight(to_tsvector('english', title), 'A') ||
    setweight(to_tsvector('english', description), 'B')
  ) STORED
);
CREATE INDEX IF NOT EXISTS tickets_search_idx ON tickets USING GIN (search_vector);

CREATE TABLE IF NOT EXISTS comments (
  id         BIGSERIAL PRIMARY KEY,
  ticket_id  BIGINT NOT NULL REFERENCES tickets(id),
  author     TEXT NOT NULL,
  body       TEXT NOT NULL CHECK (char_length(body) BETWEEN 3 AND 4000),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Same status state machine as the local server, enforced in the database.
CREATE OR REPLACE FUNCTION enforce_ticket_transition() RETURNS trigger AS $$
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  IF NOT (
    (OLD.status = 'open'        AND NEW.status IN ('in_progress','resolved','closed','duplicate')) OR
    (OLD.status = 'in_progress' AND NEW.status IN ('open','resolved','duplicate')) OR
    (OLD.status = 'resolved'    AND NEW.status IN ('closed','open')) OR
    (OLD.status IN ('closed','duplicate') AND NEW.status = 'open')
  ) THEN
    RAISE EXCEPTION 'invalid ticket transition % -> %', OLD.status, NEW.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tickets_transition ON tickets;
CREATE TRIGGER tickets_transition BEFORE UPDATE OF status ON tickets
  FOR EACH ROW EXECUTE FUNCTION enforce_ticket_transition();

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bug_app') THEN
    CREATE ROLE bug_app LOGIN;
  END IF;
END $$;
GRANT SELECT, INSERT ON tickets, comments TO bug_app;
GRANT UPDATE (status, priority, duplicate_of, updated_at) ON tickets TO bug_app;
GRANT USAGE ON SEQUENCE tickets_id_seq, comments_id_seq TO bug_app;
