"""
Gramps local database client.

Provides access to Gramps databases for genealogy research.
Works with Gramps 5.x databases (SQLite backend).

Reference: https://gramps-project.org/

SECURITY NOTE: This module uses pickle to deserialize Gramps database blobs.
Gramps uses pickle for its internal storage format - this is how Gramps stores
data in its SQLite database. Only use this with your own trusted Gramps databases.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import UUID

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    Event,
    Family,
    GenealogyDate,
    Name,
    Person,
    Place,
    Source,
    SourceLevel,
)


@dataclass
class GrampsHandle:
    """Gramps internal handle reference."""
    handle: str
    table: str


class GrampsClient:
    """
    Client for accessing local Gramps databases.

    Gramps uses SQLite for storage with a specific schema.
    This client provides read/write access following GPS standards.

    IMPORTANT: This client reads Gramps' native pickle-serialized blobs.
    Only use with your own trusted Gramps databases.
    """

    # Gramps database tables
    TABLES = {
        "person": "person",
        "family": "family",
        "event": "event",
        "place": "place",
        "source": "source",
        "citation": "citation",
        "repository": "repository",
        "media": "media",
        "note": "note",
        "tag": "tag",
    }

    def __init__(self, db_path: str | Path | None = None):
        """
        Initialize Gramps client.

        Args:
            db_path: Path to Gramps database directory or .gramps file
        """
        self.db_path = Path(db_path) if db_path else None
        self._conn: sqlite3.Connection | None = None
        self._db_file: Path | None = None

    def connect(self, db_path: str | Path | None = None) -> None:
        """
        Connect to a Gramps database.

        Args:
            db_path: Path to database (overrides constructor path)
        """
        path = Path(db_path) if db_path else self.db_path
        if not path:
            raise ValueError("No database path provided")

        # Find the SQLite database file
        if path.is_dir():
            # Gramps family tree directory structure
            self._db_file = path / "sqlite.db"
            if not self._db_file.exists():
                # Try alternate location
                self._db_file = path / "grampsdb.db"
        elif path.suffix == ".gramps":
            # Gramps archive - would need to extract
            raise NotImplementedError("Gramps archive files not yet supported")
        else:
            self._db_file = path

        if not self._db_file.exists():
            raise FileNotFoundError(f"Database not found: {self._db_file}")

        self._conn = sqlite3.connect(str(self._db_file))
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def session(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database session."""
        if not self._conn:
            raise RuntimeError("Not connected to database")
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _deserialize_blob(self, blob: bytes) -> dict[str, Any]:
        """
        Deserialize Gramps blob data.

        Gramps stores complex objects as pickled blobs in SQLite.
        This is Gramps' native format, not arbitrary untrusted data.

        For safety, we try JSON first, then fall back to pickle
        for Gramps' native format.
        """
        # Try JSON first (safer, used in some newer formats)
        try:
            return json.loads(blob.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        # Gramps uses pickle for blob storage - this is its native format.
        # Only deserialize blobs from trusted Gramps databases you own.
        # NOTE: pickle is required here as it's how Gramps stores data
        try:
            import pickle
            return pickle.loads(blob)
        except Exception:
            return {}

    def _serialize_blob(self, data: dict[str, Any]) -> bytes:
        """Serialize data to Gramps blob format."""
        # Use JSON for new data where possible
        try:
            return json.dumps(data).encode("utf-8")
        except (TypeError, ValueError):
            # Fall back to pickle for complex Gramps structures
            import pickle
            return pickle.dumps(data)

    # =========================================
    # Person Operations
    # =========================================

    def get_person(self, handle: str) -> Person | None:
        """Get a person by Gramps handle."""
        if not self._conn:
            raise RuntimeError("Not connected to database")

        cursor = self._conn.execute(
            "SELECT blob_data FROM person WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        data = self._deserialize_blob(row["blob_data"])
        return self._person_from_gramps(handle, data)

    def _person_from_gramps(self, handle: str, data: dict) -> Person:
        """Convert Gramps person data to our Person model."""
        person = Person(
            gramps_id=data.get("gramps_id"),
        )

        # Parse primary name
        primary_name = data.get("primary_name", {})
        if primary_name:
            person.names.append(Name(
                given=primary_name.get("first_name", ""),
                surname=self._get_primary_surname(primary_name),
                nickname=primary_name.get("nick", ""),
            ))

        # Alternate names
        for alt_name in data.get("alternate_names", []):
            person.names.append(Name(
                given=alt_name.get("first_name", ""),
                surname=self._get_primary_surname(alt_name),
                name_type="alias",
            ))

        # Sex
        gender = data.get("gender", 2)  # Gramps: 0=Female, 1=Male, 2=Unknown
        person.sex = {0: "F", 1: "M"}.get(gender, "U")

        # Event references would need additional lookups
        person.birth = self._get_birth_event(data.get("event_ref_list", []))
        person.death = self._get_death_event(data.get("event_ref_list", []))

        return person

    def _get_primary_surname(self, name_data: dict) -> str:
        """Extract primary surname from Gramps name structure."""
        surnames = name_data.get("surname_list", [])
        if surnames:
            return surnames[0].get("surname", "")
        return ""

    def _get_birth_event(self, event_refs: list) -> Event | None:
        """Find and parse birth event from event references."""
        for ref in event_refs:
            if ref.get("role") == "Primary":
                event_handle = ref.get("ref")
                # Would need to look up event
                # Simplified for now
                pass
        return None

    def _get_death_event(self, event_refs: list) -> Event | None:
        """Find and parse death event from event references."""
        return None  # Simplified

    def find_persons(
        self,
        surname: str | None = None,
        given: str | None = None,
        birth_year: int | None = None,
        death_year: int | None = None,
    ) -> list[Person]:
        """
        Search for persons matching criteria.

        Note: Full-text search on blobs is limited;
        for production use, consider building an index.
        """
        if not self._conn:
            raise RuntimeError("Not connected to database")

        results = []
        cursor = self._conn.execute("SELECT handle, blob_data FROM person")

        for row in cursor:
            data = self._deserialize_blob(row["blob_data"])
            person = self._person_from_gramps(row["handle"], data)

            # Filter
            if surname:
                if not person.primary_name or surname.lower() not in person.primary_name.surname.lower():
                    continue
            if given:
                if not person.primary_name or given.lower() not in person.primary_name.given.lower():
                    continue

            results.append(person)

        return results

    def add_person(self, person: Person) -> str:
        """
        Add a person to the Gramps database.

        Returns the Gramps handle.
        """
        if not self._conn:
            raise RuntimeError("Not connected to database")

        from uuid import uuid4

        handle = str(uuid4()).replace("-", "")[:20]
        gramps_id = person.gramps_id or f"I{self._get_next_id('person')}"

        # Build Gramps data structure
        data = {
            "handle": handle,
            "gramps_id": gramps_id,
            "gender": {"M": 1, "F": 0}.get(person.sex, 2),
            "primary_name": {},
            "alternate_names": [],
            "event_ref_list": [],
            "family_list": [],
            "parent_family_list": [],
            "citation_list": [],
            "note_list": [],
            "media_list": [],
            "tag_list": [],
            "private": person.is_private,
        }

        if person.primary_name:
            data["primary_name"] = {
                "first_name": person.primary_name.given,
                "surname_list": [{"surname": person.primary_name.surname}],
                "nick": person.primary_name.nickname or "",
            }

        blob_data = self._serialize_blob(data)

        with self.session():
            self._conn.execute(
                "INSERT INTO person (handle, gramps_id, blob_data) VALUES (?, ?, ?)",
                (handle, gramps_id, blob_data)
            )

        return handle

    def _get_next_id(self, table: str) -> int:
        """Get next available ID number for a table."""
        cursor = self._conn.execute(
            f"SELECT MAX(CAST(SUBSTR(gramps_id, 2) AS INTEGER)) FROM {table}"
        )
        row = cursor.fetchone()
        return (row[0] or 0) + 1

    # =========================================
    # Family Operations
    # =========================================

    def get_family(self, handle: str) -> Family | None:
        """Get a family by Gramps handle."""
        if not self._conn:
            raise RuntimeError("Not connected to database")

        cursor = self._conn.execute(
            "SELECT blob_data FROM family WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        data = self._deserialize_blob(row["blob_data"])
        return self._family_from_gramps(handle, data)

    def _family_from_gramps(self, handle: str, data: dict) -> Family:
        """Convert Gramps family data to our Family model."""
        return Family(
            gramps_id=data.get("gramps_id"),
            # husband_id and wife_id would need handle-to-UUID mapping
        )

    # =========================================
    # Source Operations
    # =========================================

    def get_source(self, handle: str) -> Source | None:
        """Get a source by Gramps handle."""
        if not self._conn:
            raise RuntimeError("Not connected to database")

        cursor = self._conn.execute(
            "SELECT blob_data FROM source WHERE handle = ?",
            (handle,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        data = self._deserialize_blob(row["blob_data"])
        return self._source_from_gramps(handle, data)

    def _source_from_gramps(self, handle: str, data: dict) -> Source:
        """Convert Gramps source data to our Source model."""
        return Source(
            title=data.get("title", ""),
            author=data.get("author", ""),
            publisher=data.get("pubinfo", ""),
            level=SourceLevel.SECONDARY,  # Default, would need classification
            source_type="unknown",
        )

    def add_source(self, source: Source) -> str:
        """Add a source to the Gramps database."""
        if not self._conn:
            raise RuntimeError("Not connected to database")

        from uuid import uuid4

        handle = str(uuid4()).replace("-", "")[:20]
        gramps_id = f"S{self._get_next_id('source')}"

        data = {
            "handle": handle,
            "gramps_id": gramps_id,
            "title": source.title,
            "author": source.author or "",
            "pubinfo": source.publisher or "",
            "note_list": [],
            "media_list": [],
            "citation_list": [],
            "reporef_list": [],
        }

        blob_data = self._serialize_blob(data)

        with self.session():
            self._conn.execute(
                "INSERT INTO source (handle, gramps_id, blob_data) VALUES (?, ?, ?)",
                (handle, gramps_id, blob_data)
            )

        return handle

    # =========================================
    # Utility Operations
    # =========================================

    def get_statistics(self) -> dict[str, int]:
        """Get database statistics."""
        if not self._conn:
            raise RuntimeError("Not connected to database")

        stats = {}
        for table in self.TABLES.values():
            try:
                cursor = self._conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats[table] = 0

        return stats

    def export_gedcom(self, output_path: str | Path) -> None:
        """
        Export database to GEDCOM format.

        Uses Gramps' built-in export if available.
        """
        # This would ideally use Gramps' export functionality
        # For now, we'd need to implement manual export
        raise NotImplementedError(
            "GEDCOM export requires Gramps Python module. "
            "Use Gramps GUI to export."
        )

    def import_gedcom(self, gedcom_path: str | Path) -> dict[str, int]:
        """
        Import a GEDCOM file into the database.

        Uses Gramps' built-in import if available.
        """
        raise NotImplementedError(
            "GEDCOM import requires Gramps Python module. "
            "Use Gramps GUI to import."
        )

    def backup(self, backup_path: str | Path) -> Path:
        """Create a backup of the database."""
        if not self._conn or not self._db_file:
            raise RuntimeError("Not connected to database")

        import shutil
        backup_path = Path(backup_path)

        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"gramps_backup_{timestamp}.db"

        # Close connection temporarily for clean copy
        self._conn.close()
        shutil.copy2(self._db_file, backup_file)
        self._conn = sqlite3.connect(str(self._db_file))
        self._conn.row_factory = sqlite3.Row

        return backup_file

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
