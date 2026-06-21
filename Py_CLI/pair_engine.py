import networkx as nx

def pair(players: dict, pairing_mode: str):
    # Pairs players for a tournament round using a Maximum Weight Matching (MWM)
    # Swiss system algorithm or a relaxed casual mode.
    # Args:
    #    players (dict): Dictionary of tournament players and their state.
    #    pairing_mode (str): "swiss" for strict chess rules, "casual" for no color parity.
    # Returns:
    #    tuple: (white_player_list, black_player_list)

    white_player_list = []; black_player_list = []

    active_players = list(players.keys()); bye_player = None

    # STEP 1: Handle Odd Number of Players

    if len(active_players) % 2 != 0:
        # Sort players descending by current score, then initial rating
        sorted_players = sorted(
            active_players,
            key=lambda p: (players[p]["score"], players[p]["rating"]),
            reverse=True
        )
        # Find lowest-ranked player who hasn't received a bye yet
        for p in reversed(sorted_players):
            if "BYE" not in players[p]["opponents"]:
                bye_player = p
                break

        if bye_player is None: bye_player = sorted_players[-1]  # Fallback

        active_players.remove(bye_player)

    # Helper to calculate color state metrics
    def get_color_metrics(p):
        history = players[p].get("color_history", [])
        w_count = history.count('W'); b_count = history.count('B')
        c_bal = w_count - b_count
        last_color = history[-1] if history else None
        return c_bal, last_color

    # Helper to evaluate if a specific color assignment is legal
    def is_legal_assignment(w_player, b_player, strict=True):
        if not strict: return True

        # Check White constraints
        w_hist = players[w_player].get("color_history", [])
        if len(w_hist) >= 2 and w_hist[-2:] == ['W', 'W']:
            return False
        w_bal, _ = get_color_metrics(w_player)
        if w_bal + 1 > 2:
            return False

        # Check Black constraints
        b_hist = players[b_player].get("color_history", [])
        if len(b_hist) >= 2 and b_hist[-2:] == ['B', 'B']:
            return False
        b_bal, _ = get_color_metrics(b_player)
        if b_bal - 1 < -2:
            return False

        return True


    # STEPS 2, 3 & 4: Graph Construction, Weights, & Matching

    # Loop through relaxation steps if a perfect matching cannot be found initially
    matching = []
    for relax_level in [0, 1, 2]:
        G = nx.Graph()
        G.add_nodes_from(active_players)

        C_score = 100000
        alpha = 1000 if relax_level == 0 else (500 if relax_level == 1 else 100)

        for i in range(len(active_players)):
            for j in range(i + 1, len(active_players)):
                u = active_players[i]
                v = active_players[j]

                # Hard Constraint: Already played (relaxed only at level 2 as absolute emergency)
                if (v in players[u]["opponents"] or u in players[v]["opponents"]) and relax_level < 2:
                    continue

                # Color Constraints (only applied strictly in Swiss mode at relax_level 0)
                if pairing_mode == "swiss" and relax_level == 0:
                    if not (is_legal_assignment(u, v, strict=True) or is_legal_assignment(v, u, strict=True)):
                        continue

                # Weight calculation
                s_u = players[u]["score"]; s_v = players[v]["score"]
                penalty_score_diff = alpha * ((s_u - s_v) ** 2)

                penalty_color = 0
                if pairing_mode == "swiss":
                    c_bal_u, lc_u = get_color_metrics(u)
                    c_bal_v, lc_v = get_color_metrics(v)
                    # Penalize if both lean toward the same color preference
                    if (c_bal_u > 0 and c_bal_v > 0) or (c_bal_u < 0 and c_bal_v < 0):
                        penalty_color += 50
                    if lc_u == lc_v and lc_u is not None:
                        penalty_color += 10

                max_rating_diff = max(abs(players[a]["rating"] - players[b]["rating"]) for a in active_players for b in active_players if a != b) or 1
                penalty_rating_diff = 10 * (abs(players[u]["rating"] - players[v]["rating"]) / max_rating_diff)

                weight = C_score - penalty_score_diff - penalty_color - penalty_rating_diff
                G.add_edge(u, v, weight=weight)

        # Execute Edmond's Blossom Algorithm via NetworkX
        matching = nx.max_weight_matching(G, maxcardinality=True)

        # Verify if all active players successfully received a match
        if len(matching) == len(active_players) // 2:
            break

    # STEP 5: Color Allocation
    matching = sorted(
        matching,
        key=lambda pair: (
            max(players[pair[0]]["score"], players[pair[1]]["score"]),
            max(players[pair[0]]["rating"], players[pair[1]]["rating"])
        ),
        reverse=True
    )

    for u, v in matching:
        if pairing_mode == "swiss":
            # Direct Structural Legality Check (Evaluated strictly first)
            u_can_be_white = is_legal_assignment(u, v, strict=True); v_can_be_white = is_legal_assignment(v, u, strict=True)

            if u_can_be_white and not v_can_be_white: white, black = u, v
            elif v_can_be_white and not u_can_be_white: white, black = v, u
            else:
                # Fallback to heuristics only when both orientations are equally valid (or invalid)
                c_bal_u, lc_u = get_color_metrics(u); c_bal_v, lc_v = get_color_metrics(v)

                if c_bal_u < c_bal_v: white, black = u, v
                elif c_bal_v < c_bal_u: white, black = v, u
                else:
                    # Tie-breaker 1: Alternation
                    if lc_u == 'B' and lc_v == 'W': white, black = u, v
                    elif lc_v == 'B' and lc_u == 'W': white, black = v, u
                    else:
                        # Tie-breaker 2: Deterministic Seeding Selections
                        if players[u]["rating"] >= players[v]["rating"]: white, black = u, v
                        else: white, black = v, u
        else:
            # Casual mode: Simple deterministic rating-based mapping
            if players[u]["rating"] >= players[v]["rating"]:  white, black = u, v
            else: white, black = v, u

        white_player_list.append(white); black_player_list.append(black)

    # Append the bye player if one was sidelined
    if bye_player is not None:
        white_player_list.append(bye_player); black_player_list.append("BYE")

    return white_player_list, black_player_list
