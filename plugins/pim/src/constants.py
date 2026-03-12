from pathlib import Path
import os

DATA_DIR = Path(os.environ.get("PIM_DATA_DIR", "~/.local/share/pim")).expanduser()
DB_PATH = DATA_DIR / "pim.db"
BLOBS_DIR = DATA_DIR / "blobs"
BACKUPS_DIR = DATA_DIR / "backups"

OBJECT_TYPES = ("note", "entry", "task", "event", "message", "contact", "resource", "topic")

REGISTERS = ("scratch", "working", "reference", "log")

RELATION_TYPES = (
    # Structural
    "belongs-to",
    # Agency
    "from", "to", "involves", "delegated-to", "sent-by", "member-of",
    # Derivation
    "derived-from",
    # Temporal
    "precedes", "occurs-during",
    # Annotation
    "annotation-of",
    # Generic
    "references", "related-to",
    # Domain-specific
    "blocks",
)

CLOSE_MODES = ("complete", "archive", "cancel", "delete")

# Write policy risk tiers
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"

# Body externalization threshold
BODY_SIZE_THRESHOLD = 100_000  # 100KB
