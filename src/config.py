import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(".env", override=True)


@dataclass(frozen=True)
class Settings:
    # Neo4j
    NEO4J_URI: str       = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str      = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str  = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str  = os.getenv("NEO4J_DATABASE", "neo4j")

    # LLM
    LLM_PROVIDER: str    = os.getenv("LLM_PROVIDER", "openai")      # or "gemini"
    LLM_MODEL: str       = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_API_KEY: str     = os.getenv("LLM_API_KEY", "")
