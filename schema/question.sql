CREATE TABLE question (
	id INTEGER PRIMARY KEY,
	uuid TEXT NOT NULL,
	owner TEXT NOT NULL,
	type TEXT NOT NULL,
	question TEXT NOT NULL,
	answer TEXT,
	asked_at INTEGER NOT NULL,
	answered_at INTEGER,
	deleted INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX uk_uuid ON question (uuid);