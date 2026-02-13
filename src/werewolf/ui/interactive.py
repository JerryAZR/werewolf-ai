"""Interactive TUI participant for human players.

Uses rich to present interactive choices during game phases.
"""

import asyncio
from typing import Optional, Protocol, Union
from rich.console import Console
from rich.prompt import Prompt
from rich.style import Style
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.align import Align

from .choices import ChoiceSpec, ChoiceType, ChoiceOption
from .prompt_session import PromptSession, PromptType, PromptStep

# Short role reminders for human players (instead of verbose system prompts)
ROLE_REMINDERS = {
    "WEREWOLF": "You are a WEREWOLF. Work with other werewolves to eliminate villagers.",
    "SEER": "You are the SEER. Check one player each night to learn their alignment.",
    "WITCH": "You are the WITCH. Use your antidote (save target) and poison (kill target) wisely.",
    "HUNTER": "You are the HUNTER. When you die, you can shoot one player.",
    "GUARD": "You are the GUARD. Protect one player each night from werewolf attacks.",
    "ORDINARY_VILLAGER": "You are a VILLAGER. Find werewolves and vote them out.",
    "VILLAGER": "You are a VILLAGER. Find werewolves and vote them out.",
}


class InteractiveParticipant:
    """A human participant using interactive TUI.

    Instead of calling an LLM, this participant presents interactive
    prompts using rich and returns properly formatted responses.

    Usage:
        participant = InteractiveParticipant(console=console)
        result = await participant.decide(
            system_prompt="...",
            user_prompt="...",
            choices=choice_spec,  # Simple ChoiceSpec
        )
        # Or for multi-step:
        result = await participant.decide(
            system_prompt="...",
            user_prompt="...",
            session=prompt_session,  # Multi-step PromptSession
        )
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        auto_number: bool = True,
        show_prompts: bool = True,
    ):
        """Initialize the interactive participant.

        Args:
            console: Rich Console instance. Creates one if None.
            auto_number: Auto-number options in selection menus
            show_prompts: Show full system/user prompts (for debugging)
        """
        self._console = console or Console()
        self._auto_number = auto_number
        self._show_prompts = show_prompts

    async def decide(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str] = None,
        choices: Optional[ChoiceSpec] = None,
        session: Optional[PromptSession] = None,
    ) -> str:
        """Make a decision via interactive TUI.

        Args:
            system_prompt: System instructions
            user_prompt: Current game state
            hint: Hint for invalid previous attempts (not typically used with TUI)
            choices: Optional simple choice specification
            session: Optional multi-step prompt session

        Returns:
            Response string formatted for handler parsing
        """
        # Session takes priority for multi-step decisions
        if session is not None:
            return await self._run_session(session, system_prompt, user_prompt)

        if choices is not None:
            return await self._choice_prompt(system_prompt, user_prompt, choices, hint)

        return await self._free_form_prompt(system_prompt, user_prompt, hint)

    async def _run_session(
        self,
        session: PromptSession,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Execute a multi-step prompt session."""
        self._show_context(system_prompt, user_prompt, None)

        while not session.is_complete():
            step = session.current_prompt()
            if step is None:
                break

            answer = await self._render_step(step)
            session.answer(answer)

        # Determine format type from steps
        if session.steps:
            first_step = session.steps[0]
            if first_step.prompt_type == PromptType.ACTION:
                format_type = "witch"
            elif first_step.prompt_type == PromptType.VOTE:
                format_type = "vote"
            else:
                format_type = "simple"
        else:
            format_type = "simple"

        return session.get_result(format_type)

    async def _render_step(self, step: PromptStep) -> str:
        """Render a single prompt step."""
        if step.prompt_type in (PromptType.SEAT, PromptType.VOTE):
            return await self._render_seat_step(step)

        elif step.prompt_type == PromptType.ACTION:
            return await self._render_action_step(step)

        elif step.prompt_type == PromptType.CONFIRM:
            return await self._render_confirm_step(step)

        elif step.prompt_type == PromptType.TEXT:
            return await self._render_text_step(step.prompt_text)

        return ""

    async def _render_seat_step(self, step: PromptStep) -> str:
        """Render a seat/vote selection step."""
        # Build a table of available seats
        table = Table(title="Available Players", show_header=True)
        table.add_column("#", width=4)
        table.add_column("Seat", width=6)
        table.add_column("Player", justify="left")

        for i, opt in enumerate(step.options):
            seat_display = f"{opt.seat_hint}" if opt.seat_hint else "—"
            player_info = opt.display
            if opt.seat_hint and opt.seat_hint in step.seat_info:
                player_info = step.seat_info[opt.seat_hint]
            table.add_row(f"[{i + 1}]", seat_display, player_info)

        if step.allow_none:
            table.add_row(f"[{len(step.options) + 1}]", "—", step.none_display)

        self._console.print(Panel(Align(table, align="center"), title=step.prompt_text))

        # Get valid selection
        max_num = len(step.options) + (1 if step.allow_none else 0)
        valid_range = range(1, max_num + 1)

        while True:
            try:
                user_input = Prompt.ask(
                    f"{step.prompt_text} (1-{max_num})",
                    console=self._console,
                )

                # Parse selection
                try:
                    idx = int(user_input) - 1
                    if idx in range(len(step.options)):
                        return step.options[idx].value
                    elif step.allow_none and idx == len(step.options):
                        return "-1"
                except ValueError:
                    pass

                # Try direct seat number
                try:
                    seat = int(user_input)
                    for opt in step.options:
                        if opt.seat_hint == seat:
                            return opt.value
                except ValueError:
                    pass

                self._console.print(f"[red]Invalid selection. Enter 1-{max_num}[/red]")

            except (KeyboardInterrupt, EOFError):
                self._console.print("\n[yellow]Defaulting to skip...[/yellow]")
                return "-1"

    async def _render_action_step(self, step: PromptStep) -> str:
        """Render an action selection step."""
        # Display options in a numbered list
        grid = Table.grid(padding=1)
        grid.add_column()

        for i, opt in enumerate(step.options):
            grid.add_row(f"[{i + 1}] {opt.display}")

        if step.allow_none:
            grid.add_row(f"[{len(step.options) + 1}] {step.none_display}")

        self._console.print(Panel(grid, title=step.prompt_text))

        max_num = len(step.options) + (1 if step.allow_none else 0)

        while True:
            try:
                user_input = Prompt.ask(
                    f"Make your choice (1-{max_num})",
                    console=self._console,
                )

                try:
                    idx = int(user_input) - 1
                    if 0 <= idx < len(step.options):
                        return step.options[idx].value
                    elif step.allow_none and idx == len(step.options):
                        return "PASS"
                except ValueError:
                    pass

                # Try matching display text
                lower_input = user_input.lower()
                for opt in step.options:
                    if lower_input == opt.display.lower():
                        return opt.value

                self._console.print(f"[red]Invalid choice. Enter 1-{max_num}[/red]")

            except (KeyboardInterrupt, EOFError):
                self._console.print("\n[yellow]Defaulting to Pass...[/yellow]")
                return "PASS"

    async def _render_confirm_step(self, step: PromptStep) -> str:
        """Render a yes/no confirmation step."""
        options = [opt.value for opt in step.options]

        while True:
            try:
                user_input = Prompt.ask(
                    f"{step.prompt_text} ({' / '.join(o.upper() for o in options)})",
                    console=self._console,
                    choices=options,
                    show_choices=False,
                )
                return user_input.lower()
            except (KeyboardInterrupt, EOFError):
                self._console.print("\n[yellow]Defaulting to No...[/yellow]")
                return "no"

    async def _render_text_step(self, prompt_text: str) -> str:
        """Render a free-form text input step."""
        try:
            return Prompt.ask(
                prompt_text,
                console=self._console,
            )
        except (KeyboardInterrupt, EOFError):
            return ""

    async def _choice_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        choices: ChoiceSpec,
        hint: Optional[str],
    ) -> str:
        """Present interactive choice prompt."""
        self._show_context(system_prompt, user_prompt, hint, choices)

        if choices.choice_type == ChoiceType.SEAT:
            return await self._prompt_seat(choices)
        elif choices.choice_type == ChoiceType.BOOLEAN:
            return await self._prompt_boolean(choices)
        elif choices.choice_type == ChoiceType.SINGLE:
            return await self._prompt_single(choices)
        else:
            return await self._free_form_prompt(system_prompt, user_prompt, hint)

    async def _prompt_seat(self, choices: ChoiceSpec) -> str:
        """Prompt for seat selection with live player info."""
        table = Table(title="Available Players", show_header=True)
        table.add_column("Option", width=6)
        table.add_column("Seat", width=6)
        table.add_column("Player", justify="left")

        for i, opt in enumerate(choices.options):
            display = opt.display
            if opt.seat_hint and choices.seat_info:
                display = choices.seat_info.get(opt.seat_hint, opt.display)
            table.add_row(f"[{i + 1}]", f"{opt.seat_hint}", display)

        if choices.allow_none:
            table.add_row(f"[{len(choices.options) + 1}]", "—", choices.none_display)

        self._console.print(Panel(Align(table, align="center"), title="Select Target"))

        max_num = len(choices.options) + (1 if choices.allow_none else 0)

        while True:
            try:
                user_input = Prompt.ask(
                    f"{choices.prompt} (1-{max_num})",
                    console=self._console,
                )

                try:
                    idx = int(user_input) - 1
                    if 0 <= idx < len(choices.options):
                        return choices.options[idx].value
                    elif choices.allow_none and idx == len(choices.options):
                        return "-1"
                except ValueError:
                    pass

                try:
                    seat = int(user_input)
                    for opt in choices.options:
                        if opt.seat_hint == seat:
                            return opt.value
                except ValueError:
                    pass

                self._console.print(f"[red]Invalid selection. Enter 1-{max_num}[/red]")

            except (KeyboardInterrupt, EOFError):
                return "-1"

    async def _prompt_boolean(self, choices: ChoiceSpec) -> str:
        """Prompt for yes/no choice."""
        options_text = " / ".join(
            f"[bold][{opt.value.upper()}][/bold] {opt.display}"
            for opt in choices.options
        )

        while True:
            try:
                user_input = Prompt.ask(
                    f"{choices.prompt} ({options_text})",
                    console=self._console,
                    choices=[opt.value for opt in choices.options],
                    show_choices=False,
                )
                return user_input.lower()
            except (KeyboardInterrupt, EOFError):
                return "no"

    async def _prompt_single(self, choices: ChoiceSpec) -> str:
        """Prompt for single choice from options."""
        grid = Table.grid(padding=1)
        grid.add_column()

        for i, opt in enumerate(choices.options):
            grid.add_row(f"[{i + 1}] {opt.display}")

        if choices.allow_none:
            grid.add_row(f"[{len(choices.options) + 1}] {choices.none_display}")

        self._console.print(Panel(grid, title=choices.prompt))

        max_num = len(choices.options) + (1 if choices.allow_none else 0)

        while True:
            try:
                user_input = Prompt.ask(
                    f"Make your choice (1-{max_num})",
                    console=self._console,
                )

                try:
                    idx = int(user_input) - 1
                    if 0 <= idx < len(choices.options):
                        return choices.options[idx].value
                    elif choices.allow_none and idx == len(choices.options):
                        return "PASS"
                except ValueError:
                    pass

                lower_input = user_input.lower()
                for opt in choices.options:
                    if lower_input == opt.display.lower():
                        return opt.value

                self._console.print(f"[red]Invalid choice. Enter 1-{max_num}[/red]")

            except (KeyboardInterrupt, EOFError):
                return "PASS"

    async def _free_form_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str],
    ) -> str:
        """Prompt for free-form text input (e.g., speeches, last words)."""
        self._show_context(system_prompt, user_prompt, hint)

        try:
            # Note: multiline not supported in older Rich versions
            return Prompt.ask(
                "Enter your response",
                console=self._console,
            )
        except (KeyboardInterrupt, EOFError):
            return ""

    def _show_context(
        self,
        system_prompt: str,
        user_prompt: str,
        hint: Optional[str],
        choices: Optional[ChoiceSpec] = None,
    ) -> None:
        """Display the game context to the player."""
        if not self._show_prompts:
            return

        # Extract role and show short reminder instead of verbose system prompt
        role_reminder = self._extract_role_reminder(system_prompt)

        self._console.print(
            Panel(
                Text(role_reminder),
                title="[bold blue]Your Role[/bold blue]",
                expand=False,
            )
        )

        # Always try to extract just the question (skip redundant options text if present)
        display_prompt = self._extract_question_only(user_prompt)

        self._console.print(
            Panel(
                Text(display_prompt),
                title="[bold green]Situation[/bold green]",
                expand=False,
            )
        )

        if hint:
            self._console.print(
                Panel(
                    Text(f"[yellow]{hint}[/yellow]"),
                    title="[bold red]Please Try Again[/bold red]",
                    expand=False,
                )
            )

    def _extract_question_only(self, user_prompt: str) -> str:
        """Extract only the question from user prompt, skip the redundant options.

        Args:
            user_prompt: Full user prompt with question and available options

        Returns:
            Just the question part
        """
        # Look for "Available options:" and截断 after it
        if "Available options:" in user_prompt:
            return user_prompt.split("Available options:")[0].strip()
        # Also handle "Options:" format
        if "Options:" in user_prompt:
            return user_prompt.split("Options:")[0].strip()
        return user_prompt

    def _extract_role_reminder(self, system_prompt: str) -> str:
        """Extract role from system prompt and return short reminder.

        Args:
            system_prompt: Full system prompt from handler

        Returns:
            Short role reminder string
        """
        # Extract role from prompts like "You are the WEREWOLF."
        for role in ROLE_REMINDERS:
            if f"You are the {role}" in system_prompt or f"You are a {role}" in system_prompt:
                return ROLE_REMINDERS[role]

        # Fallback: return first part of system prompt if no match
        first_line = system_prompt.strip().split("\n")[0]
        return first_line if first_line else "Your role"


# ============================================================================
# Factory function
# ============================================================================

def create_interactive_participant(
    console: Optional[Console] = None,
) -> InteractiveParticipant:
    """Create an interactive participant for human play."""
    return InteractiveParticipant(console=console)


__all__ = [
    "InteractiveParticipant",
    "create_interactive_participant",
]
