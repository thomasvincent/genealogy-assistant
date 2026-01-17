"""Gramps Desktop Plugin for Smart Search Router.

This tool integrates the Smart Search Router into Gramps Desktop,
allowing users to get AI-powered search recommendations directly
from within Gramps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Gramps imports - these are available when running inside Gramps
try:
    from gramps.gen.plug import Tool
    from gramps.gen.plug.menu import PersonOption
    from gramps.gui.plug import tool as tool_module

    GRAMPS_AVAILABLE = True
except ImportError:
    GRAMPS_AVAILABLE = False
    # Stub classes for type checking and testing outside Gramps
    class Tool:  # type: ignore
        pass

    class PersonOption:  # type: ignore
        pass


if TYPE_CHECKING:
    from gramps.gen.db import DbReadBase
    from gramps.gen.lib import Person as GrampsPerson


# Import our core library
from genealogy_assistant.core.models import (
    Event,
    GenealogyDate,
    Name,
    Person,
    Place,
)
from genealogy_assistant.router import SmartRouter, SourceRecommendation, SourceRegistry


class SmartSearchOptions:
    """Options for the Smart Search tool."""

    def __init__(self, name: str, person_id: str = ""):
        self.name = name
        self.person_id = person_id

    def add_menu_options(self, menu) -> None:
        """Add options to the menu."""
        person_option = PersonOption(_("Person"))
        person_option.set_help(_("Select the person to search for"))
        menu.add_option(_("Options"), "person", person_option)


class SmartSearchTool(Tool):
    """
    Gramps tool for Smart Search routing.

    Analyzes a selected person and recommends which genealogical
    databases to search based on their context.
    """

    def __init__(
        self,
        dbstate,
        user,
        options_class,
        name: str,
        callback=None,
    ):
        """Initialize the tool."""
        self.db: DbReadBase = dbstate.db
        self.user = user
        self.uistate = user.uistate if hasattr(user, "uistate") else None

        # Initialize our core router
        self.registry = SourceRegistry()
        self.router = SmartRouter(registry=self.registry, enable_ai_fallback=False)

        Tool.__init__(self, dbstate, options_class, name)

        if self.fail:
            return

        # Get selected person
        self.person_handle = self.options.handler.options_dict.get("person")

        self.run()

    def run(self) -> None:
        """Execute the tool."""
        if not self.person_handle:
            self._show_message(_("No person selected"), _("Please select a person first."))
            return

        # Get person from database
        gramps_person = self.db.get_person_from_handle(self.person_handle)
        if not gramps_person:
            self._show_message(_("Person not found"), _("Could not find the selected person."))
            return

        # Convert to our Person model
        person = self._convert_person(gramps_person)

        # Get recommendations
        recommendations = self.router.route(person=person)

        # Display results
        self._display_recommendations(gramps_person, recommendations)

    def _convert_person(self, gramps_person: GrampsPerson) -> Person:
        """Convert Gramps Person to our Person model."""
        person = Person()

        # Convert name
        primary_name = gramps_person.get_primary_name()
        if primary_name:
            name = Name(
                given=primary_name.get_first_name(),
                surname=primary_name.get_surname(),
            )
            person.names.append(name)

        # Convert birth
        birth_ref = gramps_person.get_birth_ref()
        if birth_ref:
            birth_event = self.db.get_event_from_handle(birth_ref.ref)
            if birth_event:
                person.birth = self._convert_event(birth_event)

        # Convert death
        death_ref = gramps_person.get_death_ref()
        if death_ref:
            death_event = self.db.get_event_from_handle(death_ref.ref)
            if death_event:
                person.death = self._convert_event(death_event)

        # Convert sex
        sex = gramps_person.get_gender()
        if sex == 1:  # Male
            person.sex = "M"
        elif sex == 0:  # Female
            person.sex = "F"
        else:
            person.sex = "U"

        return person

    def _convert_event(self, gramps_event) -> Event:
        """Convert Gramps Event to our Event model."""
        event = Event(event_type=str(gramps_event.get_type()))

        # Convert date
        gramps_date = gramps_event.get_date_object()
        if gramps_date and gramps_date.get_year() != 0:
            event.date = GenealogyDate(
                year=gramps_date.get_year(),
                month=gramps_date.get_month() or None,
                day=gramps_date.get_day() or None,
            )

        # Convert place
        place_handle = gramps_event.get_place_handle()
        if place_handle:
            gramps_place = self.db.get_place_from_handle(place_handle)
            if gramps_place:
                event.place = Place(name=gramps_place.get_title())

        return event

    def _display_recommendations(
        self,
        gramps_person: GrampsPerson,
        recommendations: list[SourceRecommendation],
    ) -> None:
        """Display recommendations to user."""
        if not recommendations:
            self._show_message(
                _("No Recommendations"),
                _("No specific databases found for this person's context."),
            )
            return

        # Build message
        name = gramps_person.get_primary_name().get_name()
        lines = [_("Search Recommendations for {}:").format(name), ""]

        for i, rec in enumerate(recommendations, 1):
            level = rec.source_level.value.upper()
            lines.append(f"{i}. [{level}] {rec.source_name}")
            lines.append(f"   Reason: {rec.reason}")
            if rec.url:
                lines.append(f"   URL: {rec.url}")
            lines.append("")

        self._show_message(_("Smart Search Results"), "\n".join(lines))

    def _show_message(self, title: str, message: str) -> None:
        """Show a message dialog."""
        if self.uistate and hasattr(self.uistate, "display_message"):
            self.uistate.display_message(title, message)
        else:
            print(f"\n{title}\n{'=' * len(title)}\n{message}")
