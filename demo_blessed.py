#!/usr/bin/env python
"""Demo: Blessed - Terminal capabilities and menus.

Install: pip install blessed

Run: python demo_blessed.py
"""

import sys
import io

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from blessed import Terminal
from collections import OrderedDict


def run_menu_inline(term, title, options, allow_none=False, none_label="Skip"):
    """Run an inline menu that doesn't hide context above.

    The menu appears at cursor position, context above stays visible.
    """
    current = 0
    options_list = list(options.keys())

    if allow_none:
        options_list.append(none_label)

    print(f"\n{term.bold}{title}{term.normal}")
    print("-" * len(title))

    while True:
        # Print options with highlighting
        for i, opt in enumerate(options_list):
            prefix = term.green(">") if i == current else " "
            if opt in options:
                display = f"  {prefix} [{i+1}] {opt} - {options[opt]}"
            else:
                display = f"  {prefix} [{i+1}] {opt}"
            # Clear line and print
            print(term.clear_eol + display)

        print(term.dim("UP/DOWN: navigate | ENTER: select | Q: quit (cancel)"))

        # Move cursor back to first option
        print(term.move_up * len(options_list) * 2, end="")

        key = term.inkey()

        if key == term.KEY_UP:
            current = (current - 1) % len(options_list)
        elif key == term.KEY_DOWN:
            current = (current + 1) % len(options_list)
        elif key == "\n" or key == term.KEY_ENTER:
            selected = options_list[current]
            # Clear the menu area
            for _ in range(len(options_list) * 2 + 1):
                print(term.clear_eol + term.move_down)
            print(term.move_up, end="")
            if selected in options:
                return options[selected]
            elif selected == none_label:
                return None
            return None
        elif key.lower() == "q":
            # Clear the menu area
            for _ in range(len(options_list) * 2 + 1):
                print(term.clear_eol + term.move_down)
            print(term.move_up, end="")
            return None


def run_menu(term, title, options, allow_none=False, none_label="Skip"):
    """Run a fullscreen keyboard-driven menu."""
    current = 0
    options_list = list(options.keys())

    if allow_none:
        options_list.append(none_label)

    with term.fullscreen():
        while True:
            with term.location(0, 0):
                print(term.clear)
                print(f"{term.bold}{title}{term.normal}")
                print("-" * len(title))
                print()

                for i, opt in enumerate(options_list):
                    prefix = ">" if i == current else " "
                    if opt in options:
                        display = f"{prefix} [{i+1}] {opt} - {options[opt]}"
                    else:
                        display = f"{prefix} [{i+1}] {opt}"
                    print(display)

                print()
                print(term.dim("UP/DOWN: navigate | ENTER: select | Q: quit"))

            key = term.inkey()

            if key == term.KEY_UP:
                current = (current - 1) % len(options_list)
            elif key == term.KEY_DOWN:
                current = (current + 1) % len(options_list)
            elif key == "\n" or key == term.KEY_ENTER:
                selected = options_list[current]
                if selected in options:
                    return options[selected]
                elif selected == none_label:
                    return None
                return None
            elif key.lower() == "q":
                return None


def demo_voting(term):
    """Who do you want to banish?"""
    # Show context
    print("""
[Game Context - Previous events visible above]
  Living: 0,1,3,4,5,6,7,8,9,10,11
  Dead: 2 (Werewolf)
  Sheriff: Player 5 (1.5x vote)
  Last Night: Player 2 killed, last words: "Player 7 is suspicious"
""")

    options = OrderedDict([
        ("Player 0", "Ordinary Villager"),
        ("Player 1", "Ordinary Villager"),
        ("Player 3", "Ordinary Villager"),
        ("Player 7", "Werewolf"),
        ("Player 9", "Ordinary Villager"),
    ])

    # Try inline menu first (preserves context above!)
    try:
        result = run_menu_inline(term, "Who do you want to banish?", options, allow_none=True)
    except Exception:
        # Fallback to fullscreen if inline fails
        result = run_menu(term, "Who do you want to banish?", options, allow_none=True)

    if result:
        print(f"\nYou voted for: {result}")
    else:
        print("\nYou abstained")
    return result


def demo_yes_no(term):
    """Yes/No confirmation."""
    options = OrderedDict([
        ("Yes", True),
        ("No", False),
    ])

    result = run_menu(term, "Do you want to opt out of Sheriff candidacy?", options)

    if result:
        print("\nYou chose to OPT OUT")
    else:
        print("\nYou chose to STAY in the election")
    return result


def demo_witch_action(term):
    """Multi-step witch action."""
    # Step 1: Choose action
    print("""
[Witch Info]
  Antidote: Available (can save 1 player)
  Poison: Available (can kill 1 player, cannot use on self)
  Werewolf target: Player 7
""")

    actions = OrderedDict([
        ("Pass (do nothing)", "PASS"),
        ("Antidote (save Player 7)", "ANTIDOTE"),
        ("Poison (kill a player)", "POISON"),
    ])

    try:
        action = run_menu_inline(term, "Choose your action:", actions)
    except Exception:
        action = run_menu(term, "Choose your action:", actions)

    if not action or action == "PASS":
        print("\nWitch action: PASS")
        return

    # Step 2: Choose target
    targets = OrderedDict([(f"Player {i}", str(i)) for i in [0, 1, 3, 4, 6, 8, 10, 11]])

    try:
        target = run_menu_inline(term, f"Select target for {action}:", targets)
    except Exception:
        target = run_menu(term, f"Select target for {action}:", targets)

    if target:
        print(f"\nWitch action: {action} -> Player {target}")


def demo_seat_selection(term):
    """Seat selection."""
    options = OrderedDict([(f"Player {i}", str(i)) for i in [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11]])

    try:
        result = run_menu_inline(term, "Who do you want to protect?", options, allow_none=True)
    except Exception:
        result = run_menu(term, "Who do you want to protect?", options, allow_none=True)

    if result:
        print(f"\nYou protected: Player {result}")
    else:
        print("\nYou chose to skip")
    return result


def demo_status_display(term):
    """Demo: Display status information."""
    with term.fullscreen():
        while True:
            with term.location(0, 0):
                print(term.clear)
                print(term.cyan + "WEREWOLF - Night 3" + term.normal)
                print("=" * 40)
                print()

                print(term.bold + "Living Players:" + term.normal)
                print("  [0] Player 0   [1] Player 1   [2] Player 2")
                print("  [3] Player 3   [4] Player 4   [5] Player 5")
                print("  [6] Player 6           [8] Player 8")
                print("  [9] Player 9   [10] Player 10 [11] Player 11")
                print()

                print(term.bold + "Dead Players:" + term.normal)
                print("  [7] Player 7 (Werewolf)  [12] Player 12")
                print()

                print(term.bold + "Sheriff:" + term.normal)
                print("  Player 5 (1.5x vote)")
                print()

                print(term.yellow + "Your Role: Werewolf" + term.normal)
                print()

                print(term.dim("Press Q to quit, any other key to refresh..."))

            key = term.inkey(timeout=2)
            if key.lower() == "q":
                break


def main():
    print("=" * 50)
    print("BLESSED Library Demo")
    print("=" * 50)
    print()
    print("This demo shows INLINE menus that preserve context above!")

    term = Terminal()
    try:
        # Demo voting (shows inline menu)
        print("\n--- Voting Phase (Inline Menu) ---")
        demo_voting(term)
        input("\nPress Enter to continue...")

        # Demo yes/no
        print("\n--- Opt-Out Phase ---")
        demo_yes_no(term)
        input("\nPress Enter to continue...")

        # Demo witch action
        print("\n--- Witch Action (Multi-Step) ---")
        demo_witch_action(term)
        input("\nPress Enter to continue...")

        # Demo seat selection
        print("\n--- Guard Action ---")
        demo_seat_selection(term)
        input("\nPress Enter to continue...")

        # Demo status display
        print("\n--- Full-Screen Game State ---")
        print("Showing real-time game status (auto-refresh)...")
        demo_status_display(term)

        print("\n" + "=" * 50)
        print("Demo complete!")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nCancelled by user.")


if __name__ == "__main__":
    main()
