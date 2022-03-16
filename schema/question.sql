CREATE TABLE question (
	id INTEGER PRIMARY KEY,
	uuid TEXT NOT NULL,
	owner TEXT NOT NULL,
	question_type TEXT NOT NULL,
	question TEXT NOT NULL,
	asked_at INTEGER NOT NULL,
	word_count INTEGER NOT NULL,
	answer TEXT,
	answered_at INTEGER,
	answered_by TEXT,
	deleted_at INTEGER
);

CREATE TABLE visit (
	id INTEGER PRIMARY KEY,
	uuid TEXT NOT NULL,
	last_visited_at INTEGER NOT NULL,
	visit_count INTEGER NOT NULL,
	FOREIGN KEY (uuid) REFERENCES question(uuid)
);

CREATE TABLE image (
	id INTEGER PRIMARY KEY,
	image_order INTEGER NOT NULL,
	filename TEXT NOT NULL,
	uuid TEXT NOT NULL,
	key TEXT NOT NULL,
	FOREIGN KEY (uuid) REFERENCES question(uuid)
);

CREATE UNIQUE INDEX uk_question_uuid ON question (uuid);
CREATE INDEX idx_owner_question_type_asked_at ON question (owner, question_type, asked_at);
CREATE UNIQUE INDEX uk_visit_uuid ON visit (uuid);
CREATE INDEX idx_image_uuid ON image (uuid);
