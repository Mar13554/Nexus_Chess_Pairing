import os, sys
from pathlib import Path
from json_func import read_jfile, write_jfile
from pair_engine import pair

def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"): base_path = os.path.dirname(sys._MEIPASS)
    else: base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Get Files
folder_dir = resource_path("Tournaments")

# Coloured Text
from colorama import Fore
CLR_PRIMARY = lambda text: Fore.BLUE + text    # Blue
CLR_SUCCESS = lambda text: Fore.GREEN + text   # Green
CLR_WARNING = lambda text: Fore.YELLOW + text  # Yellow
CLR_ERROR = lambda text: Fore.RED + text       # Red
CLR_INFO = lambda text: Fore.CYAN + text       # Cyan

# Global state tracker
tournament_state = {
    "players": {},           # id/name -> player data
    "max_length": 0,
    "pairing_mode": "swiss",  # "swiss" or "casual" (no color parity)
    "Rounds": []
}

res_dict = {-1: "  ---  ", 0: " 0 - 1 ", 0.5: "1/2-1/2", 1: " 1 - 0 "}
res_str = lambda res: res_dict[res]
class Round:
    def __init__(self): self.white = []; self.black = []; self.result = []; self.completed = False
    def generate(self):
        active = {k: v for k, v in tournament_state["players"].items() if not v.get("suspended", False)}
        self.white, self.black = pair(active, tournament_state["pairing_mode"])
        self.result = [-1 for i in self.white]
        if "BYE" in self.black: self.result[-1] = 1
    def result_add(self, row_id, res): self.result[row_id] = res
    def is_done(self): return -1 not in self.result

# Command Functions

def cmd_help(args):
    print("\n", CLR_PRIMARY("=== Chess Pairing Software Manual ==="))
    print(CLR_INFO("Format: [Number/Keyword] <Arguments>\n"))

    commands_help = [
        ("0", "mode", "<swiss/casual>", "Toggles color parity requirement"),
        ("1", "add", "<name> <rating>", "Registers a new player to the pool"),
        ("2", "list", "", "Prints players and result statistics"),
        ("3", "gen", "", "Validates entries and generates next round pairings"),
        ("4", "res", "<id row> <res>", "Records match result for white (1, 0, 0.5)"),
        ("5", "show", "", "Prints current round"),
        ("6", "end", "", "Ends the current round and updates scores"),
        ("7", "suspend", "<name>", "Toggles player suspension from future pairings"),
        ("s", "save", "<name>", "Saves the current tournament settings"),
        ("l", "load", "<name>", "Loads from a save in the 'Tournaments' folder"),
        ("o", "loadlist", "", "Displays the list of saves in the 'Tournaments' folder"),
        ("e", "export", "<name>", "Exports current round to html in 'Exports' folder"),
        ("h", "help", "", "Displays this instruction manual"),
        ("q", "exit", "", "Terminates the program safety")
    ]

    for num, kw, args_syntax, desc in commands_help:
        print(f"  [{num}] {kw:<8} {args_syntax:<20} - {desc}")
    print()

def cmd_toggle_mode(args):
    if not args:
        print(CLR_INFO(f"Current mode: {tournament_state['pairing_mode']}"))
        return
    mode = args[0].lower()
    if mode in ["swiss", "casual"]:
        tournament_state["pairing_mode"] = mode
        print(CLR_SUCCESS(f"Pairing mode updated to: {mode}"))
    else: print(CLR_ERROR(f"Error: Unknown mode '{mode}'. Use 'swiss' or 'casual'."))

def cmd_exit(args):
    print(CLR_INFO("Exiting pairing software. Goodbye!"))
    sys.exit(0)

def cmd_add_player(args):
    if len(args) < 1:
        print(CLR_ERROR("Error: 'add' requires at least a player name. Usage: add <name> [rating]"))
        return

    name = args[0]
    rating = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1200

    if name in tournament_state["players"]:
        print(CLR_WARNING(f"Warning: Player '{name}' is already registered."))
        return

    if len(name) > tournament_state["max_length"]: tournament_state["max_length"] = len(name)
    tournament_state["players"][name] = {
        "rating": rating,
        "score": 0.0,
        "opponents": set(),
        "color_history": [],
        "suspended": False
    }
    print(CLR_SUCCESS(f"Success: Added {name} (Rating: {rating})"))

def cmd_list_players(args):
    if not tournament_state["players"]: print(CLR_WARNING("No players registered.")); return

    col_name = max(tournament_state["max_length"], len("Player"))
    header = f"{'Player':<{col_name}} | Rating | Score | Games | Colors  | Buchholz"
    separator = "-" * len(header)
    text = f"Standings\n{separator}\n{header}\n{separator}\n"

    sorted_players = sorted(
        tournament_state["players"].items(),
        key=lambda x: (
            x[1]["score"],
            sum(tournament_state["players"][opp]["score"] for opp in x[1]["opponents"] if opp != "BYE"),
            x[1]["rating"]
        ),
        reverse=True
    )

    for name, v in sorted_players:
        history = v["color_history"]
        games = len(history)
        colors = f"W:{history.count('W')} B:{history.count('B')}" if games > 0 else "  —  "
        buchholz = sum(tournament_state["players"][opp]["score"] for opp in v["opponents"] if opp != "BYE")
        suspended_mark = " [SUSPENDED]" if v.get("suspended", False) else ""
        text += f"{name:<{col_name}} | {v['rating']:>6} | {v['score']:>5} | {games:>5} | {colors:<7} | {buchholz:.1f}{suspended_mark}\n"

    print(CLR_INFO(text))

rev_score = {0 : 1, 0.5 : 0.5, 1 : 0}
def cmd_generate_round(args):
    num_rounds = len(tournament_state["Rounds"])
    # If there is a previous round, check it is set as completed
    if num_rounds > 0:
        previous_round = tournament_state["Rounds"][-1]
        if not previous_round.completed: print(CLR_WARNING("Previous round not completed. Use command 'end' to end the previous round.")); return

    active = [k for k, v in tournament_state["players"].items() if not v.get("suspended", False)]
    if len(active) < 2: print(CLR_ERROR("Error: At least 2 active players are required to generate a round.")); return

    # Generate
    new_round = Round()
    new_round.generate()
    tournament_state["Rounds"].append(new_round)
    print(CLR_SUCCESS("Round Generated!"))

def cmd_result_change(args):
    if len(args) != 2: print(CLR_WARNING("Expected two arguments <id row> and <result>.")); return
    if not args[0].isdigit(): print(CLR_WARNING("<id row> must be a whole number.")); return
    if not tournament_state["Rounds"]: print(CLR_WARNING("No rounds exist yet.")); return
    try: result_val = float(args[1])
    except ValueError: print(CLR_WARNING("<result> should be 0, 1, or 0.5 (from white's perspective).")); return
    if result_val not in [1, 0, 0.5]: print(CLR_WARNING("<result> should be 0, 1, or 0.5 (from white's perspective).")); return
    if len(tournament_state["Rounds"][-1].result) < int(args[0]): print(CLR_WARNING("Row id does not exist.")); return
    tournament_state["Rounds"][-1].result_add(int(args[0])-1, result_val)

def cmd_show_round(args):
    num_rounds = len(tournament_state["Rounds"])
    if num_rounds == 0: print(CLR_WARNING("No current rounds.")); return

    current_round = tournament_state["Rounds"][-1]
    num_rows = len(current_round.white)
    text_margin = max((len(p) for p in current_round.white), default=0)

    header = f"Round {num_rounds}"
    separator = "-" * max(len(header), text_margin + 20)
    text = f"{header}\n{separator}\n"

    for row in range(num_rows):
        text += str(row + 1) + ") " + current_round.white[row] + (text_margin - len(current_round.white[row])) * " " + " | " + res_str(current_round.result[row]) + f" | {current_round.black[row]}\n"
    print(CLR_INFO(text))

ELO_K = 32
def calc_elo(rating_a, rating_b, score_a):
    expected = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    return round(ELO_K * (score_a - expected))

def cmd_end_round(args):
    num_rounds = len(tournament_state["Rounds"])
    # If there is a round, verify it is completed
    if num_rounds > 0:
        current_round = tournament_state["Rounds"][-1]
        if not current_round.is_done(): print(CLR_WARNING("Round results not filled, unable to end round.")); return
        if current_round.completed: print(CLR_WARNING("Round already ended.")); return
        # Update Values (Colour History and Scores)
        for i in range(0, len(current_round.white)):
            white_player_name = current_round.white[i]; black_player_name = current_round.black[i]
            tournament_state["players"][white_player_name]["score"] += current_round.result[i]
            tournament_state["players"][white_player_name]["color_history"] += ["W"]
            if black_player_name != "BYE":
                tournament_state["players"][white_player_name]["opponents"].add(black_player_name)
                tournament_state["players"][black_player_name]["opponents"].add(white_player_name)
                tournament_state["players"][black_player_name]["score"] += rev_score[current_round.result[i]]
                tournament_state["players"][black_player_name]["color_history"] += ["B"]
            else: tournament_state["players"][white_player_name]["opponents"].add("BYE")

        # Update Elo
        elo_changes = {}
        for i in range(len(current_round.white)):
            white_name = current_round.white[i]; black_name = current_round.black[i]
            if black_name == "BYE": continue
            w_change = calc_elo(tournament_state["players"][white_name]["rating"],
                                tournament_state["players"][black_name]["rating"],
                                current_round.result[i])
            b_change = calc_elo(tournament_state["players"][black_name]["rating"],
                                tournament_state["players"][white_name]["rating"],
                                rev_score[current_round.result[i]])
            elo_changes[white_name] = w_change; elo_changes[black_name] = b_change
        elo_text = "Elo Updates\n" + "-" * (tournament_state["max_length"] + 26) + "\n"
        for name, change in elo_changes.items():
            old = tournament_state["players"][name]["rating"]
            tournament_state["players"][name]["rating"] += change
            new = tournament_state["players"][name]["rating"]
            sign = "+" if change >= 0 else ""
            elo_text += f"{name:<{tournament_state['max_length']}} | {old} → {new} ({sign}{change})\n"
        print(CLR_INFO(elo_text))

        current_round.completed = True
        print(CLR_SUCCESS("Round Ended!"))
    else: print(CLR_ERROR("No round to end."))

def cmd_save_state(args):
    if not args: print(CLR_ERROR("Error: 'save' requires a filename. Usage: save <name>")); return
    # Create a 'deep' copy structure for serialization
    serialized_state = {
        "players": {},
        "max_length": tournament_state["max_length"],
        "pairing_mode": tournament_state["pairing_mode"],
        "Rounds": []
    }

    # Convert player sets to lists
    for name, player_data in tournament_state["players"].items():
        serialized_state["players"][name] = {
            "rating": player_data["rating"],
            "score": player_data["score"],
            "opponents": list(player_data["opponents"]),  # set -> list
            "color_history": player_data["color_history"],
            "suspended": player_data.get("suspended", False)
        }

    # Convert Round objects to dictionaries
    for r in tournament_state["Rounds"]:
        serialized_state["Rounds"].append({
            "white": r.white,
            "black": r.black,
            "result": r.result,
            "completed": r.completed
        })

    file_name = os.path.join(folder_dir, args[0])
    write_jfile(file_name, serialized_state)
    print(CLR_INFO(f"Saved as {file_name} successfully!"))

def cmd_load_state(args):
    if not args: print(CLR_ERROR("Error: 'load' requires a filename. Usage: load <name>")); return
    global tournament_state
    file_name = os.path.join(folder_dir, args[0])
    data = read_jfile(file_name)
    # Reconstruct primitive data
    tournament_state["max_length"] = data["max_length"]
    tournament_state["pairing_mode"] = data["pairing_mode"]

    # Reconstruct players and convert lists back to sets
    tournament_state["players"] = {}
    for name, player_data in data["players"].items():
        tournament_state["players"][name] = {
            "rating": player_data["rating"],
            "score": player_data["score"],
            "opponents": set(player_data["opponents"]),  # list -> set
            "color_history": player_data["color_history"],
            "suspended": player_data.get("suspended", False)
        }

    # Reconstruct Round class instances
    tournament_state["Rounds"] = []
    for round_data in data["Rounds"]:
        r = Round()
        r.white = round_data["white"]; r.black = round_data["black"]
        r.result = round_data["result"]; r.completed = round_data["completed"]
        tournament_state["Rounds"].append(r)
    print(CLR_INFO(f"Loaded from {file_name} successfully!"))

def cmd_loadlist(args):
    path = Path(folder_dir)
    if not path.exists(): print(CLR_INFO("No saves found (Tournaments folder does not exist yet.)")); return
    print(CLR_INFO("Saves\n---------------"))
    for item in path.iterdir():
        print(item.name)

def cmd_suspend(args):
    if len(args) < 1: print(CLR_ERROR("Error: 'suspend' requires a player name.")); return
    name = args[0]
    if name not in tournament_state["players"]: print(CLR_ERROR(f"Error: Player '{name}' not found.")); return

    player = tournament_state["players"][name]
    player["suspended"] = not player.get("suspended", False)

    if player["suspended"]: print(CLR_WARNING(f"{name} suspended, excluded from future pairings."))
    else: print(CLR_SUCCESS(f"{name} reinstated, will be included in future pairings."))

def cmd_export(args):
    num_rounds = len(tournament_state["Rounds"])
    if num_rounds == 0: print(CLR_WARNING("No rounds to export.")); return

    current_round = tournament_state["Rounds"][-1]
    if not current_round.white: print(CLR_WARNING("Current round has no pairings.")); return

    file_stem = args[0] if args else f"Round_{num_rounds}"
    export_dir = resource_path("Exports")
    os.makedirs(export_dir, exist_ok=True)
    file_name = os.path.join(export_dir, file_stem + ".html")

    # Pairing rows
    rows_html = ""
    for i in range(len(current_round.white)):
        white = current_round.white[i]
        black = current_round.black[i]
        w_rating = tournament_state["players"][white]["rating"]
        b_rating = tournament_state["players"][black]["rating"] if black != "BYE" else "—"
        shade = ' class="alt"' if i % 2 == 0 else ""
        if current_round.completed: result_cell = f'<td class="result-box result-filled">{res_str(current_round.result[i])}</td>'
        else: result_cell = '<td class="result-box"><span class="result-line"></span></td>'
        rows_html += f"""
                <tr{shade}>
                    <td class="board">{i + 1}</td>
                    <td class="player">{white}</td>
                    <td class="rating">{w_rating}</td>
                    {result_cell}
                    <td class="rating">{b_rating}</td>
                    <td class="player right">{black}</td>
                </tr>"""

    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    mode_label = tournament_state["pairing_mode"].capitalize()

    html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>Round {num_rounds} Pairings</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: Georgia, serif; background: #fff; color: #111; padding: 40px; max-width: 800px; margin: auto; }}
        header {{ border-bottom: 3px double #111; padding-bottom: 12px; margin-bottom: 24px; }}
        h1 {{ font-size: 1.8em; letter-spacing: 0.05em; }}
        .meta {{ font-size: 0.85em; color: #555; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
        th {{ font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.08em;
              border-bottom: 2px solid #111; padding: 6px 8px; text-align: center; }}
        td {{ padding: 10px 8px; font-size: 0.95em; border-bottom: 1px solid #ddd; }}
        tr.alt td {{ background: #f7f7f7; }}
        .board {{ text-align: center; font-weight: bold; width: 40px; color: #555; }}
        .player {{ width: 30%; }}
        .player.right {{ text-align: right; }}
        .rating {{ text-align: center; width: 60px; color: #666; font-size: 0.85em; }}
        .result-box {{ width: 80px; text-align: center; }}
        .result-line {{ display: block; border-bottom: 1px solid #999; margin: 0 8px; }}
        .result-filled {{ font-family: monospace; font-size: 1em; font-weight: bold; color: #111; }}
        .white-label {{ color: #888; font-size: 0.72em; display: block; margin-top: 2px; }}
        footer {{ margin-top: 32px; font-size: 0.75em; color: #aaa; text-align: center; border-top: 1px solid #ddd; padding-top: 12px; }}
        @media print {{
            body {{ padding: 20px; }}
            footer {{ position: fixed; bottom: 0; width: 100%; }}
        }}
    </style>
    </head>
    <body>
    <header>
        <h1>Round {num_rounds} — Pairings</h1>
        <div class="meta">{today} &nbsp;|&nbsp; Mode: {mode_label} &nbsp;|&nbsp; {len(tournament_state["players"])} Players</div>
    </header>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th colspan="2">White</th>
                <th>Result</th>
                <th colspan="2">Black</th>
            </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
    </table>
    <footer>Generated by Nexus Chess Pairing &mdash; {file_stem}</footer>
    </body>
    </html>"""

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(html)
    print(CLR_SUCCESS(f"Exported to {file_name}"))

# Command Dictionary
    # Both the string keyword and number point to the exact same function memory address.
COMMAND_MAP = {
    "0": cmd_toggle_mode, "mode": cmd_toggle_mode,
    "1": cmd_add_player, "add": cmd_add_player,
    "2": cmd_list_players, "list": cmd_list_players,
    "3": cmd_generate_round, "gen": cmd_generate_round,
    "4": cmd_result_change, "res": cmd_result_change,
    "5": cmd_show_round, "show": cmd_show_round,
    "6": cmd_end_round, "end": cmd_end_round,
    "7": cmd_suspend, "suspend": cmd_suspend,
    "h": cmd_help, "help": cmd_help,
    "s": cmd_save_state, "save": cmd_save_state,
    "l": cmd_load_state, "load": cmd_load_state,
    "o": cmd_loadlist, "loadlist": cmd_loadlist,
    "e": cmd_export, "export": cmd_export,
    "q": cmd_exit, "exit": cmd_exit,
}

# Main Loop
def main():
    print(CLR_SUCCESS("Nexus Chess Pairing (CLI V.1.2) Initialized."))
    print("Type 'h' or 'help' to see available commands.\n")

    while True:
        try:
            # Command indicator
            user_raw = input(f"{CLR_PRIMARY("pairing-engine>")} ").strip()
            if not user_raw: continue

            # Split input by spaces
            tokens = user_raw.split()
            command_token = tokens[0].lower()
            arguments = tokens[1:]

            # Map execution
            if command_token in COMMAND_MAP: COMMAND_MAP[command_token](arguments)
            else: print(CLR_ERROR(f"Unknown command '{command_token}'. Type 'help' for options."))
        except (KeyboardInterrupt, EOFError):
            print("\n")
            cmd_exit([])
        except ValueError: print(CLR_ERROR("Error: Invalid argument type, check your values and try again."))
        except IndexError: print(CLR_ERROR("Error: No round or player data available for that operation."))
        except FileNotFoundError as e: print(CLR_ERROR(f"Error: File not found '{e}'"))
        except KeyError as e: print(CLR_ERROR(f"Error: Player or field not found '{e}'"))
        except Exception as e: print(CLR_ERROR(f"Unexpected error: {type(e).__name__}: {e}"))

if __name__ == "__main__":
    main()
