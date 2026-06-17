"""Neo4j configuration for the knowledge graph layer."""

from __future__ import annotations

import os


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Lm15308521273")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
