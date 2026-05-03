"""
projetv1.py — Ultimate Tic-Tac-Toe : Combat IA (fichier unique)
================================================================
Contient :
  - GameState   : logique du plateau (make/undo, coups legaux, victoire)
  - Heuristics  : evaluation statique
  - MinimaxAI   : Alpha-Beta + Move Ordering + Iterative Deepening + Parallelisation Racine (Colab CPU optim)
  - Interface   : boucle CLI avec affichage COLORE pour eviter les erreurs

Contrainte stricte : max 7 secondes par coup.
"""

from __future__ import annotations
import os
import math
import time
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

Move = Tuple[int, int]          # (col, row) 0-indexes
SubGrid = Tuple[int, int]       # (sub_row, sub_col)
SubBoard = List[int]            # 9 entiers : 0=vide, 1=X, -1=O

# Codes ANSI pour les couleurs
ANSI_BG_YELLOW = "\033[43m"
ANSI_FG_BLACK = "\033[30m"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_FG_RED = "\033[31m"
ANSI_FG_GREEN = "\033[32m"
ANSI_FG_CYAN = "\033[36m"

# =========================================================================
# GameState
# =========================================================================

class GameState:
    """Etat complet du jeu. make_move / undo_move pour backtracking."""

    WIN_PATTERNS: List[Tuple[int, int, int]] = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ]

    def __init__(self) -> None:
        self.board = [[[0] * 9 for _ in range(3)] for _ in range(3)]
        self.global_board: List[List[int]] = [[0] * 3 for _ in range(3)]
        self.current_player: int = 1
        self.forced_subgrid: Optional[SubGrid] = None
        self._history: list = []

    def clone(self) -> GameState:
        """Cree une copie independante de l'etat (utile pour la parallelisation)."""
        new_state = GameState()
        new_state.board = [[[val for val in self.board[r][c]] for c in range(3)] for r in range(3)]
        new_state.global_board = [[val for val in self.global_board[r]] for r in range(3)]
        new_state.current_player = self.current_player
        new_state.forced_subgrid = self.forced_subgrid
        return new_state

    def get_cell(self, col: int, row: int) -> int:
        return self.board[row // 3][col // 3][(row % 3) * 3 + (col % 3)]

    def check_local_winner(self, sub_row: int, sub_col: int) -> int:
        b = self.board[sub_row][sub_col]
        for a, c, d in self.WIN_PATTERNS:
            if b[a] != 0 and b[a] == b[c] == b[d]:
                return b[a]
        return 2 if all(x != 0 for x in b) else 0

    def check_global_winner(self) -> int:
        flat = [self.global_board[r][c] for r in range(3) for c in range(3)]
        for a, b, c in self.WIN_PATTERNS:
            v = flat[a]
            if v not in (0, 2) and v == flat[b] == flat[c]:
                return v
        return 2 if all(x != 0 for x in flat) else 0

    def is_terminal(self) -> bool:
        return self.check_global_winner() != 0

    def get_legal_moves(self) -> List[Move]:
        if self.forced_subgrid is not None:
            sr, sc = self.forced_subgrid
            if self._is_subgrid_available(sr, sc):
                return self._get_moves_in_subgrid(sr, sc)
        moves: List[Move] = []
        for sr in range(3):
            for sc in range(3):
                if self._is_subgrid_available(sr, sc):
                    moves.extend(self._get_moves_in_subgrid(sr, sc))
        return moves

    def _get_moves_in_subgrid(self, sub_row: int, sub_col: int) -> List[Move]:
        moves: List[Move] = []
        for local_idx in range(9):
            if self.board[sub_row][sub_col][local_idx] == 0:
                lr, lc = divmod(local_idx, 3)
                moves.append((sub_col * 3 + lc, sub_row * 3 + lr))
        return moves

    def _is_subgrid_available(self, sub_row: int, sub_col: int) -> bool:
        return self.global_board[sub_row][sub_col] == 0

    def make_move(self, move: Move) -> None:
        col, row = move
        sr, sc = row // 3, col // 3
        local_idx = (row % 3) * 3 + (col % 3)
        prev_global = [r[:] for r in self.global_board]
        self._history.append((move, self.forced_subgrid, prev_global, self.current_player))
        self.board[sr][sc][local_idx] = self.current_player
        self.global_board[sr][sc] = self.check_local_winner(sr, sc)
        next_sr, next_sc = row % 3, col % 3
        self.forced_subgrid = (
            (next_sr, next_sc) if self._is_subgrid_available(next_sr, next_sc) else None
        )
        self.current_player = -self.current_player

    def undo_move(self) -> None:
        move, forced_before, global_before, player_before = self._history.pop()
        col, row = move
        self.board[row // 3][col // 3][(row % 3) * 3 + (col % 3)] = 0
        self.global_board = global_before
        self.forced_subgrid = forced_before
        self.current_player = player_before


# =========================================================================
# Heuristics
# =========================================================================

class Heuristics:
    """Evaluation statique du plateau."""

    WIN_SCORE  = 1_000_000
    DRAW_SCORE = -(WIN_SCORE - 1)

    W_LOCAL_WIN       = 3_000
    W_NEAR_GLOBAL_WIN = 1_200
    W_CENTER_GLOBAL   = 400
    W_CORNER_GLOBAL   = 150
    W_CENTER_LOCAL    = 90
    W_CORNER_LOCAL    = 45
    W_LINE_TWO        = 70
    W_LINE_ONE        = 15
    W_SEND_ACTIVE     = 80
    W_SEND_FINISHED   = 60

    @staticmethod
    def evaluate(state: GameState, maximizing_player: int) -> float:
        winner = state.check_global_winner()
        if winner == maximizing_player:
            return float(Heuristics.WIN_SCORE)
        if winner == -maximizing_player:
            return float(-Heuristics.WIN_SCORE)
        if winner == 2:
            return float(Heuristics.DRAW_SCORE)

        score = 0.0
        score += Heuristics._score_global_board(state, maximizing_player)
        score += Heuristics._score_local_boards(state, maximizing_player)
        score += Heuristics._score_sending(state, maximizing_player)
        return score

    @staticmethod
    def _score_global_board(state: GameState, player: int) -> float:
        score = 0.0
        flat = [state.global_board[r][c] for r in range(3) for c in range(3)]
        corners = (0, 2, 6, 8)
        for idx, v in enumerate(flat):
            if v == player:
                score += Heuristics.W_LOCAL_WIN
                if idx == 4: score += Heuristics.W_CENTER_GLOBAL
                if idx in corners: score += Heuristics.W_CORNER_GLOBAL
            elif v == -player:
                score -= Heuristics.W_LOCAL_WIN
                if idx == 4: score -= Heuristics.W_CENTER_GLOBAL
                if idx in corners: score -= Heuristics.W_CORNER_GLOBAL
        for a, b, c in GameState.WIN_PATTERNS:
            vals = [flat[a], flat[b], flat[c]]
            p_cnt = vals.count(player)
            o_cnt = vals.count(-player)
            free  = vals.count(0)
            if o_cnt == 0 and p_cnt == 2 and free == 1:
                score += Heuristics.W_NEAR_GLOBAL_WIN
            if p_cnt == 0 and o_cnt == 2 and free == 1:
                score -= Heuristics.W_NEAR_GLOBAL_WIN
        return score

    @staticmethod
    def _score_local_boards(state: GameState, player: int) -> float:
        score = 0.0
        corners = (0, 2, 6, 8)
        for sr in range(3):
            for sc in range(3):
                if state.global_board[sr][sc] != 0:
                    continue
                b = state.board[sr][sc]
                score += Heuristics.W_CENTER_LOCAL * (
                    (1 if b[4] == player else 0) - (1 if b[4] == -player else 0)
                )
                for idx in corners:
                    score += Heuristics.W_CORNER_LOCAL * (
                        (1 if b[idx] == player else 0) - (1 if b[idx] == -player else 0)
                    )
                for a, bi, c in GameState.WIN_PATTERNS:
                    line = (b[a], b[bi], b[c])
                    p_cnt = line.count(player)
                    o_cnt = line.count(-player)
                    empty = line.count(0)
                    if o_cnt == 0:
                        if p_cnt == 2 and empty == 1: score += Heuristics.W_LINE_TWO
                        elif p_cnt == 1 and empty == 2: score += Heuristics.W_LINE_ONE
                    if p_cnt == 0:
                        if o_cnt == 2 and empty == 1: score -= Heuristics.W_LINE_TWO
                        elif o_cnt == 1 and empty == 2: score -= Heuristics.W_LINE_ONE
        return score

    @staticmethod
    def _score_sending(state: GameState, player: int) -> float:
        fs = state.forced_subgrid
        if fs is None:
            return 0.0
        sr, sc = fs
        gv = state.global_board[sr][sc]
        if gv != 0:
            bonus = Heuristics.W_SEND_FINISHED
            return bonus if state.current_player == -player else -bonus
        b = state.board[sr][sc]
        next_player = state.current_player
        threat_count = 0
        for a, bi, c in GameState.WIN_PATTERNS:
            line = (b[a], b[bi], b[c])
            p_line = line.count(next_player)
            o_line = line.count(-next_player)
            if o_line == 0 and p_line == 2:
                threat_count += 1
        penalty = threat_count * Heuristics.W_SEND_ACTIVE
        return -penalty if next_player == -player else penalty


# =========================================================================
# MinimaxAI avec Parallelisation Racine
# =========================================================================

class MinimaxAI:
    """IA Minimax Alpha-Beta avec Iterative Deepening, Move Ordering et Parallelisation."""

    _TIME_MARGIN = 0.97

    def __init__(self, player: int = 1, time_limit: float = 6.8, max_depth: int = 15):
        self.player = player
        self.time_limit = time_limit
        self.max_depth = max_depth
        self.nodes_explored = 0
        self.depth_reached = 0
        self._start_time = 0.0
        self._time_exceeded = False
        self._lock = threading.Lock()

    def choose_move(self, state: GameState) -> Move:
        """Selectionne le meilleur coup. Sur Colab (multi-cpu), la parallelisation de la racine est un enorme gain."""
        self._reset_stats()
        legal_moves = state.get_legal_moves()

        if not legal_moves:
            raise RuntimeError("Aucun coup legal disponible.")
        if len(legal_moves) == 1:
            return legal_moves[0]

        ordered = self._order_moves(legal_moves, state)
        best_move = ordered[0]

        for depth in range(1, self.max_depth + 1):
            if self._is_time_up():
                break
            self._time_exceeded = False
            
            # PARALLELISATION DE LA RACINE
            # Sur Colab, ThreadPoolExecutor permet de lancer des evaluations en parallele
            # sur les differents coeurs CPU disponibles.
            local_best_score = -math.inf
            local_best_move = ordered[0]
            
            # Utiliser 4 workers maximum pour eviter l'overhead du thread switching
            workers = min(len(ordered), 4)
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                # Soumettre toutes les branches racines
                futures = {}
                for move in ordered:
                    # On clone l'etat pour que chaque thread ait son propre plateau
                    state_clone = state.clone()
                    state_clone.make_move(move)
                    future = executor.submit(self._alpha_beta_thread, state_clone, depth - 1, -math.inf, math.inf, False)
                    futures[future] = move

                for future in as_completed(futures):
                    if self._is_time_up():
                        self._time_exceeded = True
                        break
                    
                    move = futures[future]
                    score = future.result()
                    
                    if score > local_best_score:
                        local_best_score = score
                        local_best_move = move
                        
                    if local_best_score >= Heuristics.WIN_SCORE:
                        break

            if not self._time_exceeded:
                best_move = local_best_move
                self.depth_reached = depth
            if local_best_score >= Heuristics.WIN_SCORE:
                break

        return best_move

    def _alpha_beta_thread(self, state: GameState, depth: int, alpha: float, beta: float, maximizing: bool) -> float:
        """Point d'entree pour chaque thread."""
        return self._alpha_beta(state, depth, alpha, beta, maximizing)

    def _alpha_beta(self, state: GameState, depth: int, alpha: float, beta: float, maximizing: bool) -> float:
        with self._lock:
            self.nodes_explored += 1
            
        if state.is_terminal() or depth == 0:
            return Heuristics.evaluate(state, self.player)
        if self._is_time_up():
            self._time_exceeded = True
            return Heuristics.evaluate(state, self.player)

        legal_moves = state.get_legal_moves()
        if not legal_moves:
            return Heuristics.evaluate(state, self.player)
        ordered = self._order_moves(legal_moves, state)

        if maximizing:
            max_eval = -math.inf
            for move in ordered:
                if self._is_time_up():
                    self._time_exceeded = True
                    break
                state.make_move(move)
                ev = self._alpha_beta(state, depth - 1, alpha, beta, False)
                state.undo_move()
                max_eval = max(max_eval, ev)
                alpha = max(alpha, ev)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = math.inf
            for move in ordered:
                if self._is_time_up():
                    self._time_exceeded = True
                    break
                state.make_move(move)
                ev = self._alpha_beta(state, depth - 1, alpha, beta, True)
                state.undo_move()
                min_eval = min(min_eval, ev)
                beta = min(beta, ev)
                if beta <= alpha:
                    break
            return min_eval

    def _order_moves(self, moves: List[Move], state: GameState) -> List[Move]:
        return sorted(moves, key=lambda m: self._move_priority(m, state), reverse=True)

    def _move_priority(self, move: Move, state: GameState) -> float:
        col, row = move
        sub_row, sub_col = row // 3, col // 3
        local_idx = (row % 3) * 3 + (col % 3)
        priority = 0.0
        b_copy = state.board[sub_row][sub_col][:]
        b_copy[local_idx] = state.current_player
        for a, bi, c in GameState.WIN_PATTERNS:
            if b_copy[a] != 0 and b_copy[a] == b_copy[bi] == b_copy[c]:
                priority += 500.0
                break
        b_opp = state.board[sub_row][sub_col][:]
        b_opp[local_idx] = -state.current_player
        for a, bi, c in GameState.WIN_PATTERNS:
            if b_opp[a] != 0 and b_opp[a] == b_opp[bi] == b_opp[c]:
                priority += 300.0
                break
        next_sr, next_sc = row % 3, col % 3
        if state.global_board[next_sr][next_sc] != 0:
            priority += 120.0
        if local_idx == 4:
            priority += 80.0
        elif local_idx in (0, 2, 6, 8):
            priority += 40.0
        if sub_row == 1 and sub_col == 1:
            priority += 70.0
        return priority

    def _is_time_up(self) -> bool:
        return (time.time() - self._start_time) >= self.time_limit * self._TIME_MARGIN

    def _reset_stats(self) -> None:
        self.nodes_explored = 0
        self.depth_reached = 0
        self._time_exceeded = False
        self._start_time = time.time()


def clear_console():
    """Efface le contenu de la console (Colab ou Terminal local)."""
    try:
        from IPython.display import clear_output
        clear_output(wait=True)
    except ImportError:
        os.system('cls' if os.name == 'nt' else 'clear')

# =========================================================================
# Affichage du plateau avec COULEURS
# =========================================================================

SYMBOLS = {0: '.', 1: f'{ANSI_FG_GREEN}X{ANSI_RESET}', -1: f'{ANSI_FG_RED}O{ANSI_RESET}'}

def print_board(state: GameState) -> None:
    """Affiche le plateau 9x9 avec mise en evidence (couleur) de la sous-grille jouable."""

    print("\n     1  2  3   4  5  6   7  8  9")
    print("   +----------+---------+---------+")

    for row in range(9):
        if row > 0 and row % 3 == 0:
            print("   +----------+---------+---------+")
            
        row_str = f" {row + 1} |"
        for col in range(9):
            if col > 0 and col % 3 == 0:
                row_str += " |"
                
            # VERIFICATION : Sommes-nous dans la sous-grille forcee ?
            in_forced_subgrid = False
            if state.forced_subgrid is not None:
                fsr, fsc = state.forced_subgrid
                if fsr == row // 3 and fsc == col // 3:
                    in_forced_subgrid = True
            
            cell = state.get_cell(col, row)
            sym = SYMBOLS[cell]
            
            # APPLICATION DE LA COULEUR DE FOND SI GRILLE FORCEE
            if in_forced_subgrid:
                # Fond Jaune + Texte Noir pour que la case ressorte visuellement
                row_str += f"{ANSI_BG_YELLOW}{ANSI_FG_BLACK} {sym.replace(ANSI_FG_GREEN, '').replace(ANSI_FG_RED, '').replace(ANSI_RESET, '')} {ANSI_RESET}"
            else:
                row_str += f" {sym} "
                
        row_str += " |"
        print(row_str)

    print("   +----------+---------+---------+")

    print(f"\n  {ANSI_BOLD}[Grilles globales]{ANSI_RESET}")
    global_syms = {0: '.', 1: f'{ANSI_FG_GREEN}X{ANSI_RESET}', -1: f'{ANSI_FG_RED}O{ANSI_RESET}', 2: '='}
    for r in range(3):
        vals = [global_syms[state.global_board[r][c]] for c in range(3)]
        print(f"   {vals[0]}  {vals[1]}  {vals[2]}")

    if state.forced_subgrid is not None:
        sr, sc = state.forced_subgrid
        print(f"\n  {ANSI_BG_YELLOW}{ANSI_FG_BLACK} => A VOUS DE JOUER : Grille {sr+1} (ligne), {sc+1} (colonne) {ANSI_RESET}")
        print(f"  {ANSI_FG_CYAN}(Les cases ou vous DEVEZ jouer sont surligneés en JAUNE ci-dessus){ANSI_RESET}")
    else:
        print(f"\n  {ANSI_FG_CYAN}=> Jeu libre (n'importe quelle grille disponible){ANSI_RESET}")


# =========================================================================
# Boucle principale (compatible Google Colab)
# =========================================================================

def main():
    """Boucle de jeu principale, optimisee pour Google Colab.
    - clear_output se fait AVANT chaque affichage du plateau
    - Un input('Entree...') est ajoute apres le coup de l'IA
      pour que l'utilisateur puisse LIRE le resultat avant le clear
    - Les stats finales ne sont jamais effacees
    """
    while True:
        starter = input("\nQui commence ? (1 = Nous, 2 = Eux) : ").strip()
        if starter in ['1', '2']:
            break
        print("Erreur : Veuillez entrer 1 ou 2.")

    my_id = 1 if starter == '1' else -1
    opponent_id = -my_id

    print(f"\nConfiguration : Notre IA est {'X (joue en premier)' if my_id == 1 else 'O (joue en second)'}.")
    print("Temps de reflexion max : 7 secondes.")

    state = GameState()
    ai = MinimaxAI(player=my_id, time_limit=6.8, max_depth=15)

    move_times = []
    move_count = 0
    last_move_info = ""  # Garde en memoire l'info du dernier coup pour l'afficher apres clear

    while True:
        # --- Affichage du plateau ---
        clear_console()
        time.sleep(0.1)  # Petit delai pour que Colab rende l'UI correctement

        # Afficher l'info du dernier coup joue (avant le plateau)
        if last_move_info:
            print(last_move_info)
            print("-" * 50)

        print_board(state)

        # --- Verifier si la partie est finie ---
        winner = state.check_global_winner()
        if winner != 0:
            print("\n" + "=" * 50)
            print("          FIN DE LA PARTIE")
            print("=" * 50)
            if winner == my_id:
                print("   NOTRE IA A GAGNE !")
            elif winner == opponent_id:
                print("   L'ADVERSAIRE A GAGNE...")
            else:
                print("   MATCH NUL !")
            break

        # Verifier aussi si aucun coup n'est possible (match nul)
        if not state.get_legal_moves():
            print("\n" + "=" * 50)
            print("   MATCH NUL (plus de coups possibles) !")
            print("=" * 50)
            break

        current = state.current_player
        move_count += 1

        if current == my_id:
            # --- TOUR DE NOTRE IA ---
            print(f"\n  [Tour #{move_count}] NOTRE IA REFLECHIT...")
            start_time = time.time()

            col, row = ai.choose_move(state)

            end_time = time.time()
            duration = end_time - start_time
            move_times.append(duration)

            # Construire le message de resultat
            move_info = f"Notre IA joue : Colonne {col + 1}, Ligne {row + 1}\n"
            move_info += f"Temps de reflexion : {duration:.3f} secondes\n"
            move_info += f"Combinaisons analysees : {ai.nodes_explored:,} (Profondeur : {ai.depth_reached})"

            if duration > 7.0:
                move_info += f"\n  !! ATTENTION : depassement du temps ({duration:.1f}s > 7s) !!"

            print(move_info)

            state.make_move((col, row))
            last_move_info = f"[Dernier coup] {move_info}"

            # PAUSE : L'utilisateur doit lire le coup avant que l'ecran se clear
            # (indispensable sur Colab sinon le clear_output efface tout immediatement)
            input("\n  >> Appuyez sur Entree pour continuer...")

        else:
            # --- TOUR DE L'ADVERSAIRE ---
            print(f"\n  [Tour #{move_count}] TOUR DE L'ADVERSAIRE")

            while True:
                try:
                    move_str = input("  Entrez le coup adverse (colonne ligne, de 1 a 9) : ")
                    parts = move_str.strip().split()
                    if len(parts) != 2:
                        print("  Format invalide. Exemple : 5 5")
                        continue

                    col_input, row_input = int(parts[0]) - 1, int(parts[1]) - 1

                    if not (0 <= col_input <= 8 and 0 <= row_input <= 8):
                        print("  Coordonnees hors limites (1 a 9).")
                        continue

                    legal = state.get_legal_moves()
                    if (col_input, row_input) not in legal:
                        print("  Coup INVALIDE selon les regles. Reessayez.")
                        print(f"     Coups legaux : {[(c+1, r+1) for c, r in legal]}")
                        continue

                    state.make_move((col_input, row_input))
                    last_move_info = f"[Dernier coup] Adversaire : Colonne {col_input + 1}, Ligne {row_input + 1}"
                    break

                except ValueError:
                    print("  Entrez deux nombres entiers. Exemple : 5 5")

    # --- STATISTIQUES FINALES ---
    # On n'efface PAS l'ecran ici pour que les stats restent visibles
    print("\n" + "=" * 50)
    print("       STATISTIQUES DE TEMPS (Notre IA)")
    print("=" * 50)
    if move_times:
        print(f"  Nombre de coups joues  : {len(move_times)}")
        print(f"  Temps total cumule     : {sum(move_times):.3f}s")
        print(f"  Temps moyen par coup   : {sum(move_times)/len(move_times):.3f}s")
        print(f"  Temps le plus long     : {max(move_times):.3f}s")
        print(f"  Temps le plus court    : {min(move_times):.3f}s")
        print(f"  Coups > 5s             : {sum(1 for t in move_times if t > 5)}")
        print(f"  Coups > 7s (VIOLATION) : {sum(1 for t in move_times if t > 7)}")

        print("\n  Detail par coup :")
        for i, t in enumerate(move_times):
            flag = " !!" if t > 7.0 else ""
            print(f"    Coup {i+1:>2} : {t:.3f}s{flag}")
    else:
        print("  Aucun coup joue par notre IA.")


if __name__ == "__main__":
    main()
