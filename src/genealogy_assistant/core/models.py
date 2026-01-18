"""
Core data models for genealogy research following BCG/GPS standards.

These models enforce:
- Genealogical Proof Standard (GPS) compliance
- Source hierarchy (Primary > Secondary > Tertiary)
- Evidence classification
- Confidence scoring
- Research logging
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, AliasChoices


class ConfidenceLevel(IntEnum):
    """
    GPS-compliant confidence scoring for conclusions.

    5 - GPS-complete, no unresolved conflicts
    4 - Strong primary evidence, minor gaps
    3 - Reasonable but incomplete
    2 - Weak or circumstantial
    1 - Speculative or tradition only
    """
    SPECULATIVE = 1
    WEAK = 2
    REASONABLE = 3
    STRONG = 4
    GPS_COMPLETE = 5


class SourceLevel(str, Enum):
    """Source hierarchy per BCG standards."""
    PRIMARY = "primary"      # Created at/near time of event
    SECONDARY = "secondary"  # Derived from or interpreting primary
    TERTIARY = "tertiary"    # Indexes, databases, user trees


class EvidenceType(str, Enum):
    """Classification of evidence."""
    DIRECT = "direct"          # Explicitly answers research question
    INDIRECT = "indirect"      # Requires inference
    NEGATIVE = "negative"      # Absence of expected record


class ConclusionStatus(str, Enum):
    """Status of genealogical conclusions."""
    PROVEN = "proven"
    LIKELY = "likely"
    PROPOSED = "proposed"
    DISPROVEN = "disproven"
    UNSUBSTANTIATED = "unsubstantiated_family_lore"


class DateModifier(str, Enum):
    """GEDCOM-compliant date modifiers."""
    EXACT = "exact"
    ABOUT = "ABT"
    BEFORE = "BEF"
    AFTER = "AFT"
    BETWEEN = "BET"
    CALCULATED = "CAL"
    ESTIMATED = "EST"


class GenealogyDate(BaseModel):
    """
    GEDCOM-compliant date representation.

    Supports modifiers: ABT, BEF, AFT, BET...AND..., CAL, EST
    Format: DD MMM YYYY (e.g., "15 JAN 1862")
    """
    year: int | None = None
    month: int | None = Field(None, ge=1, le=12)
    day: int | None = Field(None, ge=1, le=31)
    modifier: DateModifier | None = DateModifier.EXACT
    end_year: int | None = None  # For BET...AND...
    end_month: int | None = None
    end_day: int | None = None
    original_text: str | None = None  # Preserve original if ambiguous

    @field_validator("modifier", mode="before")
    @classmethod
    def validate_modifier(cls, v) -> DateModifier:
        """Convert None to EXACT for backwards compatibility."""
        if v is None:
            return DateModifier.EXACT
        return v

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("month") is None:
            raise ValueError("Cannot specify day without month")
        return v

    def to_gedcom(self) -> str:
        """Convert to GEDCOM date format."""
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        parts = []
        if self.modifier != DateModifier.EXACT:
            parts.append(self.modifier.value)

        if self.day:
            parts.append(str(self.day))
        if self.month:
            parts.append(months[self.month - 1])
        if self.year:
            parts.append(str(self.year))

        if self.modifier == DateModifier.BETWEEN and self.end_year:
            parts.append("AND")
            if self.end_day:
                parts.append(str(self.end_day))
            if self.end_month:
                parts.append(months[self.end_month - 1])
            parts.append(str(self.end_year))

        return " ".join(parts)

    def to_datetime(self) -> datetime:
        """Convert to Python datetime object."""
        return datetime(
            year=self.year or 1,
            month=self.month or 1,
            day=self.day or 1
        )

    @classmethod
    def from_gedcom(cls, date_str: str) -> GenealogyDate:
        """Parse a GEDCOM date string."""
        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
        }

        parts = date_str.upper().split()
        modifier = DateModifier.EXACT
        year = month = day = None
        end_year = end_month = end_day = None

        idx = 0
        if parts and parts[0] in ["ABT", "BEF", "AFT", "BET", "CAL", "EST"]:
            modifier = DateModifier(parts[0])
            idx = 1

        # Parse main date
        while idx < len(parts) and parts[idx] != "AND":
            if parts[idx] in months:
                month = months[parts[idx]]
            elif parts[idx].isdigit():
                num = int(parts[idx])
                if num > 31:
                    year = num
                elif month is None and num <= 12:
                    # Could be day or month - assume day if < 32
                    day = num
                else:
                    day = num
            idx += 1

        # Parse end date for BET...AND...
        if modifier == DateModifier.BETWEEN and idx < len(parts) and parts[idx] == "AND":
            idx += 1
            while idx < len(parts):
                if parts[idx] in months:
                    end_month = months[parts[idx]]
                elif parts[idx].isdigit():
                    num = int(parts[idx])
                    if num > 31:
                        end_year = num
                    else:
                        end_day = num
                idx += 1

        return cls(
            year=year, month=month, day=day,
            modifier=modifier,
            end_year=end_year, end_month=end_month, end_day=end_day,
            original_text=date_str
        )


class Place(BaseModel):
    """
    GEDCOM-compliant place representation.

    Format: City, County/Province, State, Country
    """
    name: str  # Full place string
    city: str | None = None
    county: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @classmethod
    def from_string(cls, place_str: str) -> Place:
        """Parse a comma-separated place string.

        Handles formats:
        - City, Country (2 parts)
        - City, State, Country (3 parts)
        - City, County, State, Country (4 parts)
        """
        parts = [p.strip() for p in place_str.split(",")]
        if len(parts) == 2:
            # City, Country
            return cls(
                name=place_str,
                city=parts[0],
                country=parts[1],
            )
        elif len(parts) == 3:
            # City, State, Country
            return cls(
                name=place_str,
                city=parts[0],
                state=parts[1],
                country=parts[2],
            )
        else:
            # City, County, State, Country (4+ parts)
            return cls(
                name=place_str,
                city=parts[0] if len(parts) > 0 else None,
                county=parts[1] if len(parts) > 1 else None,
                state=parts[2] if len(parts) > 2 else None,
                country=parts[3] if len(parts) > 3 else None,
            )

    def to_gedcom(self) -> str:
        """Convert to GEDCOM place format."""
        return self.name


class Repository(BaseModel):
    """Archive or repository information."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    address: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class Source(BaseModel):
    """
    Genealogical source with BCG-compliant classification.

    Enforces source hierarchy:
    - PRIMARY: Created at or near time of event
    - SECONDARY: Derived from or interpreting primary
    - TERTIARY: Indexes, databases, user trees
    """
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | str = Field(default_factory=uuid4)
    title: str = ""
    author: str | None = None
    publisher: str | None = None
    publication_date: GenealogyDate | None = None
    repository: Repository | str | None = None
    call_number: str | None = None
    url: str | None = None

    level: SourceLevel = Field(
        default=SourceLevel.TERTIARY,
        validation_alias=AliasChoices("level", "source_level")
    )
    source_type: str = ""  # e.g., "civil registration", "census", "parish register"

    # For digital sources
    film_number: str | None = None  # FamilySearch film
    item_number: str | None = None
    page: str | None = None

    # Quality indicators
    is_original: bool = True  # Original vs derivative
    is_image: bool = False    # Image vs transcript/index

    notes: str | None = None
    access_date: str | date | None = None

    # Additional fields used by tests
    jurisdiction: str | None = None
    date_range: str | None = None
    provider: str | None = None  # For online databases
    original_source: str | None = None  # For derivative sources
    nara_series: str | None = None  # For US census
    nara_roll: str | None = None  # For US census
    publication_place: str | None = None  # For published sources
    entry_info: str | None = None  # Entry-specific information
    accessed_via: str | None = None  # How the source was accessed (e.g., "FamilySearch.org")

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v):
        """Accept string IDs for backwards compatibility."""
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                # Keep as string if not a valid UUID
                return v
        return v

    @property
    def source_level(self) -> SourceLevel:
        """Alias for level for backwards compatibility."""
        return self.level

    def quality_score(self) -> int:
        """Calculate source quality score (0-10)."""
        score = 0
        # Source level
        if self.level == SourceLevel.PRIMARY:
            score += 4
        elif self.level == SourceLevel.SECONDARY:
            score += 2
        # Original vs derivative
        if self.is_original:
            score += 3
        # Image vs transcript
        if self.is_image:
            score += 2
        # Has repository
        if self.repository:
            score += 1
        return min(score, 10)


class Citation(BaseModel):
    """
    Source citation linking evidence to a source.

    Supports Evidence Explained citation format.
    """
    id: UUID | str = Field(default_factory=uuid4)
    source_id: UUID | str

    # Specific location within source
    page: str | None = None
    entry_number: str | None = None
    item_of_interest: str | None = None

    # Evidence classification
    evidence_type: EvidenceType = EvidenceType.DIRECT

    # What the citation proves
    fact_proven: str = ""

    # Transcription/abstract
    transcription: str | None = None
    abstract: str | None = None

    # Assessment
    reliability_notes: str | None = None
    conflicts_with: list[UUID | str] = Field(default_factory=list)

    date_accessed: date = Field(default_factory=date.today)

    # Additional fields for backwards compatibility
    detail: str | None = None  # Alias for item_of_interest
    quality: str | None = None  # Quality assessment string

    @field_validator("id", "source_id", mode="before")
    @classmethod
    def validate_ids(cls, v):
        """Accept string IDs for backwards compatibility."""
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return v
        return v


class Event(BaseModel):
    """A genealogical event (birth, death, marriage, etc.)."""
    id: UUID = Field(default_factory=uuid4)
    event_type: str  # BIRT, DEAT, MARR, BURI, OCCU, RESI, etc.
    date: GenealogyDate | None = None
    place: Place | None = None
    description: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.REASONABLE
    notes: str | None = None

    @property
    def sources(self) -> list:
        """Return source IDs from citations for backwards compatibility."""
        return [c.source_id for c in self.citations]


class Name(BaseModel):
    """
    Person's name with variants and sources.

    Handles:
    - Given name variants (Jean/John, François/Frank)
    - Surname variants (HERINCKX/HERINCX/HERINKX)
    - Nicknames
    - Maiden vs married names
    """
    id: UUID = Field(default_factory=uuid4)
    given: str
    surname: str
    suffix: str | None = None
    prefix: str | None = None
    nickname: str | None = None

    # For women
    maiden_name: str | None = None

    # Name type
    name_type: Literal["birth", "married", "adopted", "alias", "immigrant"] = "birth"

    # Variants encountered in records
    variants: list[str] = Field(default_factory=list)

    # Sources for this name
    citations: list[Citation] = Field(default_factory=list)

    def full_name(self) -> str:
        """Return full name string.

        Format: Given [Nickname] [Prefix] SURNAME [Suffix]
        Example: "Johannes van den BERG Jr."
        """
        parts = []
        parts.append(self.given)
        if self.nickname:
            parts.append(f'"{self.nickname}"')
        if self.prefix:
            parts.append(self.prefix)
        parts.append(self.surname)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)

    def gedcom_name(self) -> str:
        """Return GEDCOM-formatted name: Given /Surname/"""
        return f"{self.given} /{self.surname}/"


class Person(BaseModel):
    """
    Individual person in the genealogy database.

    Follows GEDCOM structure with GPS compliance.
    """
    id: UUID | str = Field(default_factory=uuid4)
    gramps_id: str | None = None  # Gramps handle
    gedcom_id: str | None = None  # @I###@ format

    # Names (can have multiple)
    names: list[Name] = Field(default_factory=list)

    # Vital events
    sex: Literal["M", "F", "U"] = "U"
    birth: Event | None = None
    christening: Event | None = None  # Baptism/christening event
    death: Event | None = None
    burial: Event | None = None

    # Other events
    events: list[Event] = Field(default_factory=list)

    # Family links
    parent_family_ids: list[UUID | str] = Field(default_factory=list)  # FAMC
    spouse_family_ids: list[UUID | str] = Field(default_factory=list)  # FAMS

    # Research metadata
    citations: list[Citation] = Field(default_factory=list)
    notes: str | None = None
    occupation: str | None = None  # Primary occupation

    # GPS compliance
    conclusion_status: ConclusionStatus = ConclusionStatus.PROPOSED
    confidence: ConfidenceLevel = ConfidenceLevel.REASONABLE

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v):
        """Accept string IDs for backwards compatibility."""
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return v
        return v

    # Flags
    is_living: bool = False
    is_private: bool = False

    @property
    def primary_name(self) -> Name | None:
        """Get the primary (birth) name."""
        for name in self.names:
            if name.name_type == "birth":
                return name
        return self.names[0] if self.names else None

    def add_name_variant(self, variant: str) -> None:
        """Add a surname spelling variant."""
        if self.primary_name and variant not in self.primary_name.variants:
            self.primary_name.variants.append(variant)

    def birth_year(self) -> int | None:
        """Extract birth year if known."""
        if self.birth and self.birth.date:
            return self.birth.date.year
        return None

    def death_year(self) -> int | None:
        """Extract death year if known."""
        if self.death and self.death.date:
            return self.death.date.year
        return None


class Family(BaseModel):
    """
    Family unit linking individuals.

    Represents a marriage/partnership and children.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: UUID | str = Field(default_factory=uuid4)
    gramps_id: str | None = None
    gedcom_id: str | None = None  # @F###@ format

    # Partners
    husband_id: UUID | str | None = None
    wife_id: UUID | str | None = None

    # Marriage event
    marriage: Event | None = None
    divorce: Event | None = None

    # Children (ordered by birth)
    children_ids: list[UUID | str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("children_ids", "child_ids")
    )

    # Relationship type
    relationship_type: Literal["married", "unmarried", "unknown"] = "married"

    # Research metadata
    citations: list[Citation] = Field(default_factory=list)
    notes: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.REASONABLE

    @field_validator("id", "husband_id", "wife_id", mode="before")
    @classmethod
    def validate_ids(cls, v):
        """Accept string IDs for backwards compatibility."""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError:
                return v
        return v

    @field_validator("children_ids", mode="before")
    @classmethod
    def validate_children_ids(cls, v):
        """Accept list of string IDs for backwards compatibility."""
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                try:
                    result.append(UUID(item))
                except ValueError:
                    result.append(item)
            else:
                result.append(item)
        return result

    @model_validator(mode="after")
    def validate_family(self) -> "Family":
        """Ensure family has at least one parent or child."""
        if not self.husband_id and not self.wife_id and not self.children_ids:
            raise ValueError("Family must have at least one member")
        return self

    @property
    def child_ids(self) -> list[UUID | str]:
        """Alias for children_ids for backwards compatibility."""
        return self.children_ids


class ResearchLogEntry(BaseModel):
    """
    Single entry in the research log.

    Per GPS standards, ALL searches must be logged including negative results.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    date: datetime = Field(default_factory=datetime.now)

    # What was searched
    person_searched: str = ""
    repository: str = ""
    collection: str = ""
    record_type: str = ""

    # Search parameters
    search_parameters: dict[str, str] = Field(default_factory=dict)
    date_range: str | None = None

    # Result
    result: Literal["positive", "negative", "inconclusive"] = "positive"
    result_description: str = Field(
        default="",
        validation_alias=AliasChoices("result_description", "result_summary")
    )

    # Source classification
    source_level: SourceLevel | None = None

    # Follow-up
    next_action: str | None = None

    # For negative evidence analysis
    absence_explanation: str | None = None

    # Backwards compatibility fields
    search_description: str | None = None  # Alternative to collection/record_type
    negative_result: bool | None = None  # Converts to result field
    notes: str | None = None  # Additional notes on the search

    @model_validator(mode="after")
    def convert_legacy_fields(self) -> "ResearchLogEntry":
        """Convert legacy negative_result to result field."""
        if self.negative_result is not None:
            self.result = "negative" if self.negative_result else "positive"
        return self

    @property
    def result_summary(self) -> str:
        """Alias for result_description for backwards compatibility."""
        return self.result_description


class ResearchLog(BaseModel):
    """
    Complete research log for a research question or lineage.

    Maintains audit trail per GPS requirements.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    research_question: str = ""
    target_person: str | None = None
    target_family: str | None = None

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    entries: list[ResearchLogEntry] = Field(default_factory=list)

    # Summary
    status: Literal["in_progress", "completed", "blocked"] = "in_progress"
    blocking_reason: str | None = None

    # Backwards compatibility
    subject: str | None = None  # Legacy field, maps to research_question
    objective: str | None = None  # Legacy field, maps to research_question

    @model_validator(mode="after")
    def convert_legacy_fields(self) -> "ResearchLog":
        """Convert legacy subject/objective to research_question."""
        if not self.research_question:
            if self.subject:
                self.research_question = self.subject
            elif self.objective:
                self.research_question = self.objective
        return self

    def add_entry(self, entry: ResearchLogEntry) -> None:
        """Add a new log entry."""
        self.entries.append(entry)
        self.updated_at = datetime.now()

    def positive_results(self) -> list[ResearchLogEntry]:
        """Get all positive search results."""
        return [e for e in self.entries if e.result == "positive"]

    def negative_results(self) -> list[ResearchLogEntry]:
        """Get all negative search results."""
        return [e for e in self.entries if e.result == "negative"]


class ProofSummary(BaseModel):
    """
    GPS-compliant proof summary for a conclusion.

    Required elements:
    1. Research question
    2. Evidence considered (primary first)
    3. Conflicts identified and resolution
    4. Final conclusion with justification
    """
    model_config = ConfigDict(populate_by_name=True)

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)

    # The question being answered
    research_question: str = ""

    # Evidence hierarchy
    primary_evidence: list[Citation] = Field(default_factory=list)
    secondary_evidence: list[Citation] = Field(default_factory=list)
    tertiary_evidence: list[Citation] = Field(default_factory=list)
    negative_evidence: list[Citation] = Field(default_factory=list)

    # Conflict resolution
    conflicts_identified: list[str | dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("conflicts_identified", "conflicts")
    )
    conflict_resolution: str | None = None

    # Conclusion
    conclusion: str = ""
    conclusion_status: ConclusionStatus = Field(
        default=ConclusionStatus.PROPOSED,
        validation_alias=AliasChoices("conclusion_status", "status")
    )
    confidence: ConfidenceLevel = ConfidenceLevel.REASONABLE

    # Justification
    reasoning: str = ""

    # Research completeness
    exhaustive_search_completed: bool = Field(
        default=False,
        validation_alias=AliasChoices("exhaustive_search_completed", "exhaustive_search")
    )
    repositories_searched: list[str] = Field(default_factory=list)

    # AI transparency
    ai_assisted: bool = False
    ai_assistance_description: str | None = None

    # Backwards compatibility - simplified evidence format
    sources: list[str] = Field(default_factory=list)  # List of source IDs
    evidence: list[dict] = Field(default_factory=list)  # List of evidence dicts

    @property
    def exhaustive_search(self) -> bool:
        """Alias for exhaustive_search_completed for backwards compatibility."""
        return self.exhaustive_search_completed

    @property
    def conflicts(self) -> list[str | dict]:
        """Alias for conflicts_identified for backwards compatibility."""
        return self.conflicts_identified

    @property
    def status(self) -> ConclusionStatus:
        """Alias for conclusion_status for backwards compatibility."""
        return self.conclusion_status

    def is_gps_compliant(self) -> bool:
        """Check if proof summary meets GPS requirements."""
        has_evidence = len(self.primary_evidence) > 0 or len(self.sources) > 0
        return (
            self.exhaustive_search_completed
            and has_evidence
            and (not self.conflicts_identified or self.conflict_resolution)
            and self.confidence >= ConfidenceLevel.STRONG
        )


class ConflictAlert(BaseModel):
    """Alert for detected data conflicts or sanity check failures."""
    id: UUID = Field(default_factory=uuid4)
    detected_at: datetime = Field(default_factory=datetime.now)

    conflict_type: Literal[
        "impossible_date",
        "overlapping_marriages",
        "conflicting_death_burial",
        "unsourced_ethnicity",
        "same_name_collision",
        "circular_reference",
        "missing_parent_link"
    ]

    severity: Literal["error", "warning", "info"]
    description: str
    affected_records: list[UUID] = Field(default_factory=list)

    # Resolution
    resolved: bool = False
    resolution: str | None = None
    resolved_at: datetime | None = None
