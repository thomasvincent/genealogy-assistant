"""
Research Log Report generation.

Creates detailed research logs documenting all searches and findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from genealogy_assistant.core.models import ResearchLog, ResearchLogEntry


@dataclass
class ResearchLogReport:
    """
    Generates formatted research log reports.

    Research logs are essential for GPS compliance, documenting
    all repositories searched and results found.
    """

    research_log: ResearchLog
    title: str = "Research Log"
    researcher: str = ""
    format: Literal["markdown", "html", "csv"] = "markdown"

    def generate(self) -> str:
        """Generate the research log report."""
        if self.format == "markdown":
            return self._generate_markdown()
        elif self.format == "html":
            return self._generate_html()
        elif self.format == "csv":
            return self._generate_csv()
        else:
            raise NotImplementedError(f"Format {self.format} not supported")

    def _generate_markdown(self) -> str:
        """Generate Markdown format report."""
        lines = []

        # Header
        lines.append(f"# {self.title}")
        lines.append("")
        if self.researcher:
            lines.append(f"**Researcher:** {self.researcher}")
        if self.research_log.subject:
            lines.append(f"**Subject:** {self.research_log.subject}")
        if self.research_log.objective:
            lines.append(f"**Objective:** {self.research_log.objective}")
        lines.append(f"**Date Range:** {self._get_date_range()}")
        lines.append(f"**Total Entries:** {len(self.research_log.entries)}")
        lines.append("")

        # Summary Statistics
        lines.append("## Summary")
        lines.append("")
        lines.extend(self._generate_summary())
        lines.append("")

        # Entries by Repository
        lines.append("## Entries by Repository")
        lines.append("")
        lines.extend(self._generate_by_repository())
        lines.append("")

        # Detailed Log
        lines.append("## Detailed Log")
        lines.append("")
        lines.append("| Date | Repository | Search | Result | Source Level |")
        lines.append("|------|------------|--------|--------|--------------|")

        for entry in sorted(self.research_log.entries, key=lambda e: e.date or datetime.min):
            date = entry.date.strftime("%Y-%m-%d") if entry.date else "-"
            repo = entry.repository or "-"
            search = self._truncate(entry.search_description or "-", 40)
            result = self._truncate(entry.result_summary or "-", 40)
            level = entry.source_level.value if entry.source_level else "-"

            lines.append(f"| {date} | {repo} | {search} | {result} | {level} |")

        lines.append("")

        # Negative Results (important for GPS)
        lines.append("## Negative Results")
        lines.append("")
        lines.append("*Documenting negative results is essential for demonstrating exhaustive research.*")
        lines.append("")

        negative = [e for e in self.research_log.entries if e.negative_result]
        if negative:
            for entry in negative:
                date = entry.date.strftime("%Y-%m-%d") if entry.date else "-"
                lines.append(f"- **{date}** - {entry.repository}: {entry.search_description}")
                if entry.notes:
                    lines.append(f"  - Note: {entry.notes}")
        else:
            lines.append("*No negative results logged*")

        lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Research log maintained according to BCG standards for GPS compliance.*")

        return "\n".join(lines)

    def _generate_summary(self) -> list[str]:
        """Generate summary statistics."""
        lines = []

        # Count by repository
        repos = {}
        for entry in self.research_log.entries:
            repo = entry.repository or "Unknown"
            repos[repo] = repos.get(repo, 0) + 1

        lines.append(f"- **Repositories searched:** {len(repos)}")

        # Count by source level
        levels = {}
        for entry in self.research_log.entries:
            if entry.source_level:
                level = entry.source_level.value
                levels[level] = levels.get(level, 0) + 1

        if levels:
            lines.append("- **Sources by level:**")
            for level, count in sorted(levels.items()):
                lines.append(f"  - {level}: {count}")

        # Count successful vs negative
        negative_count = sum(1 for e in self.research_log.entries if e.negative_result)
        positive_count = len(self.research_log.entries) - negative_count

        lines.append(f"- **Positive results:** {positive_count}")
        lines.append(f"- **Negative results:** {negative_count}")

        return lines

    def _generate_by_repository(self) -> list[str]:
        """Generate entries grouped by repository."""
        lines = []

        # Group entries by repository
        by_repo = {}
        for entry in self.research_log.entries:
            repo = entry.repository or "Unknown"
            if repo not in by_repo:
                by_repo[repo] = []
            by_repo[repo].append(entry)

        for repo, entries in sorted(by_repo.items()):
            lines.append(f"### {repo}")
            lines.append("")
            lines.append(f"*{len(entries)} searches*")
            lines.append("")

            for entry in entries:
                date = entry.date.strftime("%Y-%m-%d") if entry.date else "-"
                status = "❌" if entry.negative_result else "✅"
                lines.append(f"- {status} **{date}**: {entry.search_description or '-'}")
                if entry.result_summary:
                    lines.append(f"  - Result: {entry.result_summary}")

            lines.append("")

        return lines

    def _generate_html(self) -> str:
        """Generate HTML format report."""
        md_content = self._generate_markdown()

        # Simple conversion (reuse from ProofSummaryReport)
        import re

        html_body = md_content
        html_body = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_body, flags=re.MULTILINE)
        html_body = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_body, flags=re.MULTILINE)
        html_body = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_body, flags=re.MULTILINE)
        html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
        html_body = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_body)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{self.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""

        return html

    def _generate_csv(self) -> str:
        """Generate CSV format report."""
        lines = ["Date,Repository,Search Description,Result,Source Level,Negative Result,Notes"]

        for entry in self.research_log.entries:
            date = entry.date.strftime("%Y-%m-%d") if entry.date else ""
            repo = self._csv_escape(entry.repository or "")
            search = self._csv_escape(entry.search_description or "")
            result = self._csv_escape(entry.result_summary or "")
            level = entry.source_level.value if entry.source_level else ""
            negative = "Yes" if entry.negative_result else "No"
            notes = self._csv_escape(entry.notes or "")

            lines.append(f"{date},{repo},{search},{result},{level},{negative},{notes}")

        return "\n".join(lines)

    def _get_date_range(self) -> str:
        """Get date range of entries."""
        dates = [e.date for e in self.research_log.entries if e.date]
        if not dates:
            return "No dates recorded"

        min_date = min(dates).strftime("%Y-%m-%d")
        max_date = max(dates).strftime("%Y-%m-%d")

        if min_date == max_date:
            return min_date
        return f"{min_date} to {max_date}"

    def _truncate(self, text: str, length: int) -> str:
        """Truncate text to length."""
        if len(text) <= length:
            return text
        return text[:length - 3] + "..."

    def _csv_escape(self, text: str) -> str:
        """Escape text for CSV."""
        if "," in text or '"' in text or "\n" in text:
            return '"' + text.replace('"', '""') + '"'
        return text

    def save(self, path: str | Path) -> None:
        """Save report to file."""
        path = Path(path)
        content = self.generate()

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
