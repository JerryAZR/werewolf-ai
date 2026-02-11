#!/usr/bin/env python
"""Demo: Pick library - Simple arrow key selection.

Install: pip install pick

Run: python demo_pick.py
"""

import sys
import io

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pick import pick


def demo_voting():
    """Who do you want to banish?"""
    # Show context BEFORE menu (important info user needs to see)
    print("""
[Game Context - Visible before menu]
  Living: 0,1,3,4,5,6,7,8,9,10,11
  Dead: 2 (Werewolf)
  Sheriff: Player 5 (1.5x vote)
  Last Night: Player 2 killed, last words: "Player 7 is suspicious"
""")

    title = "Who do you want to banish?"
    options = [
        "Player 0 (Ordinary Villager)",
        "Player 1 (Ordinary Villager)",
        "Player 3 (Ordinary Villager)",
        "Player 7 (Werewolf)",
        "Player 9 (Ordinary Villager)",
        "Skip / Abstain",
    ]

    option, index = pick(options, title, indicator="=>")
    print(f"\nYou voted for: {option}")
    return index


def demo_yes_no():
    """Yes/No confirmation."""
    title = "Do you want to opt out of Sheriff candidacy?"
    options = ["Yes", "No"]

    option, index = pick(options, title, indicator="=>")
    print(f"\nYou chose: {option}")
    return index


def demo_witch_action():
    """Multi-step witch action."""
    # Step 1: Choose action
    title = "Choose your action:"
    actions = [
        "Pass (do nothing)",
        "Antidote (save Player 7)",
        "Poison (kill a player)",
    ]

    action, action_idx = pick(actions, title, indicator="=>")

    if action_idx == 0:
        print("\nWitch action: PASS")
        return

    # Step 2: Choose target
    title = f"Select target for {action.split('(')[0].strip()}:"
    targets = [
        "Player 0",
        "Player 1",
        "Player 3",
        "Player 4",
        "Player 6",
        "Player 8",
        "Player 10",
        "Player 11",
    ]

    target, _ = pick(targets, title, indicator="=>")
    print(f"\nWitch action: {action.split('(')[0].strip()} -> {target}")


def demo_seat_selection():
    """Seat selection with info."""
    title = "Who do you want to protect?"
    options = [
        f"Player {i}" for i in [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11]
    ]

    option, index = pick(options, title, indicator="=>")
    print(f"\nYou protected: {option}")


def main():
    print("=" * 50)
    print("PICK Library Demo")
    print("=" * 50)
    print("\nUse UP/DOWN arrows, ENTER to confirm, ESC to cancel\n")

    try:
        # Demo voting
        print("\n--- Voting Phase ---")
        demo_voting()
        input("\nPress Enter to continue...")

        # Demo yes/no
        print("\n--- Opt-Out Phase ---")
        demo_yes_no()
        input("\nPress Enter to continue...")

        # Demo witch action
        print("\n--- Witch Action (Multi-Step) ---")
        demo_witch_action()
        input("\nPress Enter to continue...")

        # Demo seat selection
        print("\n--- Guard Action ---")
        demo_seat_selection()

        print("\n" + "=" * 50)
        print("Demo complete!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nCancelled by user.")


if __name__ == "__main__":
    main()
