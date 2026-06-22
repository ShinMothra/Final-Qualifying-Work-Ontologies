CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontologies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ontology_versions (
    id SERIAL PRIMARY KEY,
    ontology_id INTEGER REFERENCES ontologies(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    owl_data TEXT NOT NULL,
    comment TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ontology_id, version)
);

CREATE INDEX idx_ontology_versions_ontology ON ontology_versions(ontology_id);
CREATE INDEX idx_ontology_name ON ontologies(name);


INSERT INTO users (username, full_name) VALUES ('admin', 'Администратор');