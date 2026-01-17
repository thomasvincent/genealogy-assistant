"""
GPS Proof Summary Report generation.

Creates formal proof summaries following BCG certification standards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from genealogy_assistant.core.models import (
    ConfidenceLevel,
    ConclusionStatus,
    Person,
    ProofSummary,
    Source,
    Citation,
    ResearchLog,
)


@dataclass
class ProofSummaryReport:
    """
    Generates GPS-compliant proof summary reports.

    A proof summary presents the case for a genealogical conclusion,
    demonstrating that GPS requirements have been met.
    """

    # Report metadata
    title: str
    researcher: str
    date: datetime = field(default_factory=datetime.now)

    # Subject
    subject: Person | None = None
    research_question: str = ""

    # GPS Elements
    proof_summary: ProofSummary | None = None
    research_log: ResearchLog | None = None

    # Output settings
    format: Literal["markdown", "html", "pdf"] = "markdown"

    def generate(self) -> str:
        """Generate the proof summary report."""
        if self.format == "markdown":
            return self._generate_markdown()
        elif self.format == "html":
            return self._generate_html()
        else:
            raise NotImplementedError(f"Format {self.format} not yet implemented")

    def _generate_markdown(self) -> str:
        """Generate Markdown format report."""
        lines = []

        # Header
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"**Researcher:** {self.researcher}")
        lines.append(f"**Date:** {self.date.strftime('%d %B %Y')}")
        lines.append("")

        # Research Question
        lines.append("## Research Question")
        lines.append("")
        lines.append(self.research_question)
        lines.append("")

        # Subject Information
        if self.subject:
            lines.append("## Subject")
            lines.append("")
            lines.extend(self._format_person_markdown(self.subject))
            lines.append("")

        # GPS Compliance Checklist
        lines.append("## GPS Compliance")
        lines.append("")
        if self.proof_summary:
            lines.extend(self._format_gps_checklist())
        else:
            lines.append("*Proof summary not yet completed*")
        lines.append("")

        # Evidence Summary
        lines.append("## Evidence Summary")
        lines.append("")
        if self.proof_summary and self.proof_summary.evidence:
            for i, evidence in enumerate(self.proof_summary.evidence, 1):
                lines.append(f"### Evidence {i}")
                lines.append("")
                lines.append(f"**Source:** {evidence.get('source', 'Unknown')}")
                lines.append(f"**Information:** {evidence.get('information', '')}")
                lines.append(f"**Quality:** {evidence.get('quality', 'Unknown')}")
                lines.append("")
        else:
            lines.append("*No evidence documented*")
        lines.append("")

        # Conflicts and Resolution
        lines.append("## Conflicts and Resolution")
        lines.append("")
        if self.proof_summary and self.proof_summary.conflicts:
            for conflict in self.proof_summary.conflicts:
                lines.append(f"- **Conflict:** {conflict.get('description', '')}")
                lines.append(f"  **Resolution:** {conflict.get('resolution', 'Unresolved')}")
                lines.append("")
        else:
            lines.append("*No conflicts identified*")
        lines.append("")

        # Conclusion
        lines.append("## Conclusion")
        lines.append("")
        if self.proof_summary:
            status_badge = self._get_status_badge(self.proof_summary.status)
            confidence_badge = self._get_confidence_badge(self.proof_summary.confidence)

            lines.append(f"**Status:** {status_badge}")
            lines.append(f"**Confidence Level:** {confidence_badge}")
            lines.append("")
            lines.append(self.proof_summary.conclusion)
        else:
            lines.append("*Conclusion pending*")
        lines.append("")

        # Research Log Summary
        lines.append("## Research Log")
        lines.append("")
        if self.research_log and self.research_log.entries:
            lines.append("| Date | Repository | Search | Result |")
            lines.append("|------|------------|--------|--------|")
            for entry in self.research_log.entries[:20]:
                date = entry.date.strftime("%Y-%m-%d") if entry.date else "-"
                lines.append(f"| {date} | {entry.repository or '-'} | {entry.search_description or '-'} | {entry.result_summary or '-'} |")
            if len(self.research_log.entries) > 20:
                lines.append(f"| ... | *{len(self.research_log.entries) - 20} more entries* | | |")
        else:
            lines.append("*No research log entries*")
        lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This proof summary follows the Genealogical Proof Standard (GPS) as defined by the Board for Certification of Genealogists.*")

        return "\n".join(lines)

    def _format_person_markdown(self, person: Person) -> list[str]:
        """Format person details for Markdown."""
        lines = []

        if person.primary_name:
            lines.append(f"**Name:** {person.primary_name.full_name()}")
            if person.primary_name.variants:
                lines.append(f"**Name Variants:** {', '.join(person.primary_name.variants)}")

        if person.birth:
            birth_parts = []
            if person.birth.date:
                birth_parts.append(person.birth.date.to_gedcom())
            if person.birth.place:
                birth_parts.append(person.birth.place.name)
            if birth_parts:
                lines.append(f"**Birth:** {', '.join(birth_parts)}")

        if person.death:
            death_parts = []
            if person.death.date:
                death_parts.append(person.death.date.to_gedcom())
            if person.death.place:
                death_parts.append(person.death.place.name)
            if death_parts:
                lines.append(f"**Death:** {', '.join(death_parts)}")

        return lines

    def _format_gps_checklist(self) -> list[str]:
        """Format GPS compliance checklist."""
        lines = []
        ps = self.proof_summary

        # GPS Element 1: Reasonably Exhaustive Research
        exhaustive = ps.exhaustive_search if ps else False
        check1 = "✅" if exhaustive else "❌"
        lines.append(f"{check1} **Reasonably Exhaustive Research**")
        if ps and ps.repositories_searched:
            lines.append(f"   - Repositories searched: {len(ps.repositories_searched)}")

        # GPS Element 2: Complete Citations
        citations_complete = ps and len(ps.sources) > 0
        check2 = "✅" if citations_complete else "❌"
        lines.append(f"{check2} **Complete and Accurate Citations**")
        if ps:
            lines.append(f"   - Sources cited: {len(ps.sources)}")

        # GPS Element 3: Analysis of Evidence
        analysis_done = ps and len(ps.evidence) > 0
        check3 = "✅" if analysis_done else "❌"
        lines.append(f"{check3} **Analysis and Correlation of Evidence**")
        if ps:
            lines.append(f"   - Evidence items analyzed: {len(ps.evidence)}")

        # GPS Element 4: Conflict Resolution
        conflicts_resolved = ps and all(
            c.get("resolution") for c in ps.conflicts
        ) if ps and ps.conflicts else True
        check4 = "✅" if conflicts_resolved else "❌"
        lines.append(f"{check4} **Resolution of Conflicting Evidence**")
        if ps and ps.conflicts:
            resolved = sum(1 for c in ps.conflicts if c.get("resolution"))
            lines.append(f"   - Conflicts resolved: {resolved}/{len(ps.conflicts)}")

        # GPS Element 5: Written Conclusion
        has_conclusion = ps and ps.conclusion
        check5 = "✅" if has_conclusion else "❌"
        lines.append(f"{check5} **Sound, Written Conclusion**")

        return lines

    def _get_status_badge(self, status: ConclusionStatus) -> str:
        """Get status badge text."""
        badges = {
            ConclusionStatus.PROVEN: "🟢 PROVEN",
            ConclusionStatus.LIKELY: "🔵 LIKELY",
            ConclusionStatus.PROPOSED: "🟡 PROPOSED",
            ConclusionStatus.DISPROVEN: "🔴 DISPROVEN",
            ConclusionStatus.UNSUBSTANTIATED: "⚪ UNSUBSTANTIATED FAMILY LORE",
        }
        return badges.get(status, str(status.value))

    def _get_confidence_badge(self, confidence: ConfidenceLevel) -> str:
        """Get confidence badge text."""
        badges = {
            ConfidenceLevel.GPS_COMPLETE: "⭐⭐⭐⭐⭐ GPS Complete (5/5)",
            ConfidenceLevel.STRONG: "⭐⭐⭐⭐ Strong (4/5)",
            ConfidenceLevel.REASONABLE: "⭐⭐⭐ Reasonable (3/5)",
            ConfidenceLevel.WEAK: "⭐⭐ Weak (2/5)",
            ConfidenceLevel.SPECULATIVE: "⭐ Speculative (1/5)",
        }
        return badges.get(confidence, str(confidence.value))

    def _generate_html(self) -> str:
        """Generate HTML format report."""
        # Convert Markdown to HTML
        md_content = self._generate_markdown()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
        body {{
            font-family: Georgia, 'Times New Roman', serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
        }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
        h2 {{ color: #444; margin-top: 2rem; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .gps-check {{ font-size: 1.2em; }}
        .proven {{ color: green; }}
        .disproven {{ color: red; }}
        .proposed {{ color: orange; }}
        footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ccc; font-size: 0.9em; color: #666; }}
    </style>
</head>
<body>
    <article>
        {self._markdown_to_html(md_content)}
    </article>
</body>
</html>"""

        return html

    def _markdown_to_html(self, md: str) -> str:
        """Simple Markdown to HTML conversion."""
        import re

        html = md

        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # Line breaks
        html = re.sub(r'\n\n', r'</p><p>', html)
        html = f'<p>{html}</p>'

        # Horizontal rules
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)

        return html

    def save(self, path: str | Path) -> None:
        """Save report to file."""
        path = Path(path)
        content = self.generate()

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
