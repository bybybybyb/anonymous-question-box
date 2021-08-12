CREATE TABLE question (
	id INTEGER PRIMARY KEY,
	uuid TEXT NOT NULL,
	owner TEXT NOT NULL,
	question_type TEXT NOT NULL,
	question TEXT NOT NULL,
	word_count INTEGER NOT NULL,
	answer TEXT,
	asked_at INTEGER NOT NULL,
	answered_at INTEGER,
	deleted_at INTEGER
);

CREATE UNIQUE INDEX uk_uuid ON question (uuid);
CREATE INDEX idx_owner_question_type_asked_at ON question (owner, question_type, asked_at);