#!/usr/bin/env python
"""Demo: Prompt Toolkit - Feature-rich interactive selection.

Install: pip install prompt_toolkit

Run: python demo_prompt_toolkit.py
"""

import sys
import io

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import radiolist_dialog, confirm


def demo_voting():
    """Who do you want to banish?"""
    options = [
        ("0", "Player 0 (Ordinary Villager)"),
        ("1", "Player 1 (Ordinary Villager)"),
        ("3", "Player 3 (Ordinary Villager)"),
        ("7", "Player 7 (Werewolf)"),
        ("9", "Player 9 (Ordinary Villager)"),
        ("skip", "Skip / Abstain"),
    ]

    result = radiolist_dialog(
        title="Voting Phase",
        text="Who do you want to banish?",
        options=options,
    ).run()

    if result is None:
        print("\nCancelled")
        return None
    elif result == "skip":
        print("\nYou abstained")
        return None
    else:
        print(f"\nYou voted for: Player {result}")
        return result


def demo_yes_no():
    """Yes/No confirmation."""
    result = confirm(
        "Do you want to opt out of Sheriff candidacy?",
        default=False,
    ).run()

    if result:
        print("\nYou chose to OPT OUT")
    else:
        print("\nYou chose to STAY in the election")
    return result


def demo_witch_action():
    """Multi-step witch action."""
    # Step 1: Choose action
    options = [
        ("PASS", "Pass (do nothing)"),
        ("ANTIDOTE", "Antidote (save Player 7)"),
        ("POISON", "Poison (kill a player)"),
    ]

    action = radiolist_dialog(
        title="Witch Action",
        text="Choose your action:",
        options=options,
    ).run()

    if action is None:
        print("\nCancelled")
        return

    if action == "PASS":
        print("\nWitch action: PASS")
        return

    # Step 2: Choose target
    target_options = [
        (str(i), f"Player {i}") for i in [0, 1, 3, 4, 6, 8, 10, 11]
    ]

    target = radiolist_dialog(
        title="Witch Action",
        text=f"Select target for {action}:",
        options=target_options,
    ).run()

    if target is None:
        print("\nCancelled")
        return

    print(f"\nWitch action: {action} -> Player {target}")


def demo_seat_selection():
    """Seat selection."""
    options = [
        (str(i), f"Player {i}") for i in [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11]
    ]

    result = radiolist_dialog(
        title="Guard Action",
        text="Who do you want to protect?",
        options=options,
    ).run()

    if result is None:
        print("\nCancelled")
        return None
    else:
        print(f"\nYou protected: Player {result}")
        return result


def demo_colored_menu():
    """Custom styled menu with radio list."""
    # Custom styling
    style = Style.from_dict({
        "dialog": "bg:#333333",
        "dialog frame": "bg:#444444",
        "dialog body": "bg:#444444 fg:white",
        "button": "bg:#555555 fg:white",
        "checkbox": "bg:#444444 fg:white",
        "radiobutton": "bg:#444444 fg:white",
        "selected": "bg:#666666 fg:green",
    })

    options = [
        ("a", "Option A"),
        ("b", "Option B"),
        ("c", "Option C"),
    ]

    result = radiolist_dialog(
        title="Styled Menu",
        text="Choose with custom colors:",
        options=options,
        style=style,
    ).run()

    if result:
        print(f"\nYou selected: {result}")


def main():
    print("=" * 50)
    print("PROMPT TOOLKIT Demo")
    print("=" * 50)
    print("\nUse UP/DOWN arrows, SPACE to select, ENTER to confirm\n")

    try:
        # Demo voting
        print("\n--- Voting Phase ---")
        demo_voting()
        input("\nPress Enter to continue...")

        # Demo yes/no
        print("\n--- Opt-Out Phase ---")
        demo_yes_no()
        input("\nEnter to continue...")

        # Demo witch action
        print("\n--- Witch Action (Multi-Step) ---")
        demo_witch_action()
        input("\nPress Enter to continue...")

        # Demo seat selection
        print("\n--- Guard Action ---")
        demo_seat_selection()
        input("\nPress Enter to continue...")

        # Demo styled menu
        print("\n--- Custom Styled Menu ---")
        demo_colored_menu()

        print("\n" + "=" * 50)
        print("Demo complete!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nCancelled by user.")


if __name__ == "__main__":
    main()
