"""
projetv1.py — Ultimate Tic-Tac-Toe : Combat IA (fichier unique, optimise Colab)
================================================================================
Optimisations :
  - Parallelisation du 1er niveau Minimax via concurrent.futures
  - Numpy pour les operations sur les tableaux de jeu
  - clear_output Colab (IPython) ou os.system en fallback
  - ANSI colors pour la grille forcee (surlignage jaune)
Convention : colonne et ligne de 1 a 9.
Contrainte : max 7 secondes par coup.
"""

from __future__ import annotations

import os
import math
import time
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Colab clear
try:
    from IPython.display import clear_output as _ipython_clear
    _IN_COLAB = True
except ImportError:
    _IN_COLAB = False

# ── Types ──────────────────────────────────────────────────────────────────
Move    = Tuple[int, int]
SubGrid = Tuple[int, int]

# ── ANSI Colors ────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
YELLOW  = "\033[93m"   # case dans la grille forcee
CYAN    = "\033[96m"   # separateur grille forcee
GREEN   = "\033[92m"   # X
RED     = "\033[91m"   # O
DIM     = "\033[2m"    # grilles terminees

WIN_PATTERNS: List[Tuple[int, int, int]] = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6),
]

# =============================================================================
# GameState
# =============================================================================

class GameState:
    """Etat complet du jeu. make_move/undo_move pour backtracking sans copie."""

    WIN_PATTERNS = WIN_PATTERNS

    def __init__(self) -> None:
        # board[sr][sc] = liste 9 cases (0/1/-1)
        self.board = [[[0]*9 for _ in range(3)] for _ in range(3)]
        self.global_board: List[List[int]] = [[0]*3 for _ in range(3)]
        self.current_player: int = 1
        self.forced_subgrid: Optional[SubGrid] = None
        self._history: list = []

    def get_cell(self, col: int, row: int) -> int:
        return self.board[row//3][col//3][(row%3)*3+(col%3)]

    def check_local_winner(self, sr: int, sc: int) -> int:
        b = self.board[sr][sc]
        for a,c,d in WIN_PATTERNS:
            if b[a] != 0 and b[a] == b[c] == b[d]:
                return b[a]
        return 2 if all(x!=0 for x in b) else 0

    def check_global_winner(self) -> int:
        flat = [self.global_board[r][c] for r in range(3) for c in range(3)]
        for a,b,c in WIN_PATTERNS:
            v = flat[a]
            if v not in (0,2) and v == flat[b] == flat[c]:
                return v
        return 2 if all(x!=0 for x in flat) else 0

    def is_terminal(self) -> bool:
        return self.check_global_winner() != 0

    def get_legal_moves(self) -> List[Move]:
        if self.forced_subgrid is not None:
            sr, sc = self.forced_subgrid
            if self.global_board[sr][sc] == 0:
                return self._moves_in(sr, sc)
        moves: List[Move] = []
        for sr in range(3):
            for sc in range(3):
                if self.global_board[sr][sc] == 0:
                    moves.extend(self._moves_in(sr, sc))
        return moves

    def _moves_in(self, sr: int, sc: int) -> List[Move]:
        moves = []
        for i in range(9):
            if self.board[sr][sc][i] == 0:
                lr, lc = divmod(i, 3)
                moves.append((sc*3+lc, sr*3+lr))
        return moves

    def make_move(self, move: Move) -> None:
        col, row = move
        sr, sc = row//3, col//3
        li = (row%3)*3+(col%3)
        prev_global = [r[:] for r in self.global_board]
        self._history.append((move, self.forced_subgrid, prev_global, self.current_player))
        self.board[sr][sc][li] = self.current_player
        self.global_board[sr][sc] = self.check_local_winner(sr, sc)
        nsr, nsc = row%3, col%3
        self.forced_subgrid = (nsr, nsc) if self.global_board[nsr][nsc] == 0 else None
        self.current_player = -self.current_player

    def undo_move(self) -> None:
        move, fs, gb, p = self._history.pop()
        col, row = move
        self.board[row//3][col//3][(row%3)*3+(col%3)] = 0
        self.global_board = gb
        self.forced_subgrid = fs
        self.current_player = p

    def clone(self) -> "GameState":
        g = GameState.__new__(GameState)
        g.board = [[sg[:] for sg in row] for row in self.board]
        g.global_board = [r[:] for r in self.global_board]
        g.current_player = self.current_player
        g.forced_subgrid = self.forced_subgrid
        g._history = []
        return g


# =============================================================================
# Heuristics
# =============================================================================

class Heuristics:
    WIN_SCORE  = 1_000_000
    DRAW_SCORE = -999_999

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
    def evaluate(state: GameState, player: int) -> float:
        w = state.check_global_winner()
        if w == player:   return float(Heuristics.WIN_SCORE)
        if w == -player:  return float(-Heuristics.WIN_SCORE)
        if w == 2:        return float(Heuristics.DRAW_SCORE)
        score = 0.0
        score += Heuristics._global(state, player)
        score += Heuristics._local(state, player)
        score += Heuristics._send(state, player)
        return score

    @staticmethod
    def _global(state: GameState, player: int) -> float:
        score = 0.0
        flat = [state.global_board[r][c] for r in range(3) for c in range(3)]
        CORNERS = (0,2,6,8)
        for idx, v in enumerate(flat):
            if v == player:
                score += Heuristics.W_LOCAL_WIN
                if idx == 4:         score += Heuristics.W_CENTER_GLOBAL
                if idx in CORNERS:   score += Heuristics.W_CORNER_GLOBAL
            elif v == -player:
                score -= Heuristics.W_LOCAL_WIN
                if idx == 4:         score -= Heuristics.W_CENTER_GLOBAL
                if idx in CORNERS:   score -= Heuristics.W_CORNER_GLOBAL
        for a,b,c in WIN_PATTERNS:
            vals = [flat[a], flat[b], flat[c]]
            pc = vals.count(player); oc = vals.count(-player); fr = vals.count(0)
            if oc==0 and pc==2 and fr==1: score += Heuristics.W_NEAR_GLOBAL_WIN
            if pc==0 and oc==2 and fr==1: score -= Heuristics.W_NEAR_GLOBAL_WIN
        return score

    @staticmethod
    def _local(state: GameState, player: int) -> float:
        score = 0.0
        CORNERS = (0,2,6,8)
        for sr in range(3):
            for sc in range(3):
                if state.global_board[sr][sc] != 0: continue
                b = state.board[sr][sc]
                score += Heuristics.W_CENTER_LOCAL * ((1 if b[4]==player else 0) - (1 if b[4]==-player else 0))
                for i in CORNERS:
                    score += Heuristics.W_CORNER_LOCAL * ((1 if b[i]==player else 0) - (1 if b[i]==-player else 0))
                for a,bi,c in WIN_PATTERNS:
                    line = (b[a], b[bi], b[c])
                    pc = line.count(player); oc = line.count(-player); em = line.count(0)
                    if oc==0:
                        if pc==2 and em==1: score += Heuristics.W_LINE_TWO
                        elif pc==1 and em==2: score += Heuristics.W_LINE_ONE
                    if pc==0:
                        if oc==2 and em==1: score -= Heuristics.W_LINE_TWO
                        elif oc==1 and em==2: score -= Heuristics.W_LINE_ONE
        return score

    @staticmethod
    def _send(state: GameState, player: int) -> float:
        fs = state.forced_subgrid
        if fs is None: return 0.0
        sr, sc = fs
        gv = state.global_board[sr][sc]
        if gv != 0:
            b = Heuristics.W_SEND_FINISHED
            return b if state.current_player == -player else -b
        b = state.board[sr][sc]
        np_ = state.current_player
        tc = sum(1 for a,bi,c in WIN_PATTERNS
                 if b[a]==b[bi]==np_ and b[c]==0 or
                    b[a]==b[c]==np_ and b[bi]==0 or
                    b[bi]==b[c]==np_ and b[a]==0)
        pen = tc * Heuristics.W_SEND_ACTIVE
        return -pen if np_ == -player else pen


# =============================================================================
# MinimaxAI — optimise avec parallelisation du 1er niveau
# =============================================================================

class MinimaxAI:
    """
    Minimax Alpha-Beta + Iterative Deepening + Move Ordering.
    Le premier niveau de recherche est parallelise via ThreadPoolExecutor
    (chaque coup racine est evalue sur un clone independant du GameState).
    """
    _TIME_MARGIN = 0.96

    def __init__(self, player: int = 1, time_limit: float = 6.8, max_depth: int = 15):
        self.player     = player
        self.time_limit = time_limit
        self.max_depth  = max_depth
        # Stats (thread-safe via lock)
        self._lock          = threading.Lock()
        self.nodes_explored = 0
        self.depth_reached  = 0
        self._start_time    = 0.0
        self._time_exceeded = False

    def choose_move(self, state: GameState) -> Move:
        self._start_time    = time.time()
        self.nodes_explored = 0
        self.depth_reached  = 0
        self._time_exceeded = False

        legal = state.get_legal_moves()
        if not legal:
            raise RuntimeError("Aucun coup legal disponible.")
        if len(legal) == 1:
            return legal[0]

        ordered = self._order_moves(legal, state)
        best_move = ordered[0]

        for depth in range(1, self.max_depth + 1):
            if self._is_time_up(): break
            self._time_exceeded = False

            # Parallelisation du premier niveau
            result_move, complete = self._parallel_root(ordered, state, depth)

            if complete:
                best_move = result_move
                self.depth_reached = depth
            if self._time_exceeded and not complete:
                break

        return best_move

    def _parallel_root(self, ordered: List[Move], state: GameState, depth: int) -> Tuple[Move, bool]:
        """Evalue chaque coup racine en parallele sur des clones independants."""
        best_score = -math.inf
        best_move  = ordered[0]
        complete   = True

        # Nombre de workers = min(nb coups, 4) pour ne pas saturer
        workers = min(len(ordered), 4)

        def eval_move(move: Move) -> Tuple[Move, float]:
            clone = state.clone()
            clone.make_move(move)
            score = self._alpha_beta(clone, depth - 1, -math.inf, math.inf, False)
            return move, score

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(eval_move, m): m for m in ordered}
            for fut in as_completed(futures):
                if self._is_time_up():
                    complete = False
                    ex.shutdown(wait=False, cancel_futures=True)
                    break
                move, score = fut.result()
                if score > best_score:
                    best_score = score
                    best_move  = move
                if best_score >= Heuristics.WIN_SCORE:
                    ex.shutdown(wait=False, cancel_futures=True)
                    break

        return best_move, complete

    def _alpha_beta(self, state: GameState, depth: int, alpha: float, beta: float, maximizing: bool) -> float:
        with self._lock:
            self.nodes_explored += 1

        if state.is_terminal() or depth == 0:
            return Heuristics.evaluate(state, self.player)
        if self._is_time_up():
            self._time_exceeded = True
            return Heuristics.evaluate(state, self.player)

        legal = state.get_legal_moves()
        if not legal:
            return Heuristics.evaluate(state, self.player)
        ordered = self._order_moves(legal, state)

        if maximizing:
            v = -math.inf
            for m in ordered:
                if self._is_time_up():
                    self._time_exceeded = True
                    break
                state.make_move(m)
                v = max(v, self._alpha_beta(state, depth-1, alpha, beta, False))
                state.undo_move()
                alpha = max(alpha, v)
                if beta <= alpha: break
            return v
        else:
            v = math.inf
            for m in ordered:
                if self._is_time_up():
                    self._time_exceeded = True
                    break
                state.make_move(m)
                v = min(v, self._alpha_beta(state, depth-1, alpha, beta, True))
                state.undo_move()
                beta = min(beta, v)
                if beta <= alpha: break
            return v

    def _order_moves(self, moves: List[Move], state: GameState) -> List[Move]:
        return sorted(moves, key=lambda m: self._priority(m, state), reverse=True)

    def _priority(self, move: Move, state: GameState) -> float:
        col, row = move
        sr, sc = row//3, col//3
        li = (row%3)*3+(col%3)
        pri = 0.0
        b  = state.board[sr][sc]
        # Gagne la sous-grille ?
        bc = b[:]; bc[li] = state.current_player
        for a,bi,c in WIN_PATTERNS:
            if bc[a]!=0 and bc[a]==bc[bi]==bc[c]: pri += 500; break
        # Bloque l'adversaire ?
        bo = b[:]; bo[li] = -state.current_player
        for a,bi,c in WIN_PATTERNS:
            if bo[a]!=0 and bo[a]==bo[bi]==bo[c]: pri += 300; break
        # Envoie vers grille terminee ?
        nsr, nsc = row%3, col%3
        if state.global_board[nsr][nsc] != 0: pri += 120
        # Centre local / coin ?
        if li == 4:            pri += 80
        elif li in (0,2,6,8):  pri += 40
        # Sous-grille centrale ?
        if sr==1 and sc==1:    pri += 70
        return pri

    def _is_time_up(self) -> bool:
        return (time.time() - self._start_time) >= self.time_limit * self._TIME_MARGIN


# =============================================================================
# Affichage avec couleurs ANSI
# =============================================================================

def clear_console():
    if _IN_COLAB:
        _ipython_clear(wait=True)
    else:
        os.system('cls' if os.name == 'nt' else 'clear')


def _cell_str(val: int, is_forced_sg: bool) -> str:
    """Retourne la chaine coloree d'une case."""
    sym = {0: '.', 1: 'X', -1: 'O'}[val]
    if val == 1:
        s = f"{GREEN}{BOLD}{sym}{RESET}"
    elif val == -1:
        s = f"{RED}{BOLD}{sym}{RESET}"
    else:
        s = sym

    if is_forced_sg:
        return f"{YELLOW}{BOLD} {s if val != 0 else '·'} {RESET}"
    return f" {s} "


def print_board(state: GameState) -> None:
    fs = state.forced_subgrid  # (sr, sc) ou None

    def sep(forced_row: bool) -> str:
        if forced_row:
            return f"   {CYAN}+----------+---------+---------+{RESET}"
        return   "   +----------+---------+---------+"

    print()
    print(f"     {BOLD}1  2  3   4  5  6   7  8  9{RESET}")

    for row in range(9):
        sr = row // 3
        # separateur horizontal
        if row == 0:
            forced_top = fs is not None and fs[0] == sr
            print(sep(forced_top))
        elif row % 3 == 0:
            # separateur entre blocs de sous-grilles
            prev_sr = (row-1) // 3
            cur_sr  = row // 3
            forced_here = fs is not None and (fs[0] == prev_sr or fs[0] == cur_sr)
            print(sep(forced_here))

        row_str = f" {row+1} |"
        for col in range(9):
            sc = col // 3
            is_forced = (fs is not None and fs == (sr, sc))
            if col > 0 and col % 3 == 0:
                if fs is not None and (fs[1] == sc-1 or fs[1] == sc):
                    row_str += f" {CYAN}|{RESET}"
                else:
                    row_str += " |"
            row_str += _cell_str(state.get_cell(col, row), is_forced)
        row_str += " |"
        print(row_str)

    # derniere ligne de separation
    if fs is not None and fs[0] == 2:
        print(sep(True))
    else:
        print(sep(False))

    # Etat grilles globales
    global_syms = {0: f"{DIM}.{RESET}", 1: f"{GREEN}{BOLD}X{RESET}",
                   -1: f"{RED}{BOLD}O{RESET}", 2: f"{DIM}={RESET}"}
    print(f"\n  [Grilles globales]")
    for r in range(3):
        vals = [global_syms[state.global_board[r][c]] for c in range(3)]
        print(f"   {vals[0]}  {vals[1]}  {vals[2]}")

    if fs is not None:
        sr, sc = fs
        print(f"\n  {YELLOW}{BOLD}=> JOUER dans la grille : ligne {sr+1}, colonne {sc+1}{RESET}")
    else:
        print(f"\n  => Jeu libre (n'importe quelle grille disponible)")


# =============================================================================
# Boucle principale
# =============================================================================

def main():
    print(f"\n{BOLD}{'='*50}{RESET}")
    print(f"{BOLD}   BATTLE IA : ULTIMATE TIC-TAC-TOE{RESET}")
    print(f"{BOLD}{'='*50}{RESET}")

    while True:
        starter = input("\nQui commence ? (1 = Nous, 2 = Eux) : ").strip()
        if starter in ['1', '2']:
            break
        print("Erreur : Veuillez entrer 1 ou 2.")

    my_id       = 1 if starter == '1' else -1
    opponent_id = -my_id
    sym_me      = f"{GREEN}X{RESET}" if my_id == 1 else f"{RED}O{RESET}"

    print(f"\nNotre IA : {sym_me}  |  Temps max : 7s")

    state = GameState()
    ai    = MinimaxAI(player=my_id, time_limit=6.8, max_depth=15)

    move_times: List[float] = []
    move_count = 0

    while True:
        clear_console()
        print_board(state)

        winner = state.check_global_winner()
        if winner != 0:
            print(f"\n{'='*50}")
            print("          FIN DE LA PARTIE")
            print(f"{'='*50}")
            if winner == my_id:
                print(f"  {GREEN}{BOLD}NOTRE IA A GAGNE !{RESET}")
            elif winner == opponent_id:
                print(f"  {RED}L'ADVERSAIRE A GAGNE...{RESET}")
            else:
                print("  MATCH NUL !")
            break

        current = state.current_player
        move_count += 1

        if current == my_id:
            print(f"\n  [Tour #{move_count}] {BOLD}NOTRE IA REFLECHIT...{RESET}")
            t0 = time.time()

            col, row = ai.choose_move(state)

            duration = time.time() - t0
            move_times.append(duration)

            bar = "▓" * int(duration / 7.0 * 20)
            print(f"  Notre IA joue : Colonne {col+1}, Ligne {row+1}")
            print(f"  Temps : {duration:.3f}s  [{bar:<20}]  profondeur={ai.depth_reached}  noeuds={ai.nodes_explored:,}")
            if duration > 7.0:
                print(f"  {RED}ATTENTION : depassement ({duration:.1f}s > 7s){RESET}")

            state.make_move((col, row))

        else:
            print(f"\n  [Tour #{move_count}] {BOLD}TOUR DE L'ADVERSAIRE{RESET}")
            while True:
                try:
                    move_str = input("  Coup adverse (colonne ligne, 1-9) : ")
                    parts = move_str.strip().split()
                    if len(parts) != 2:
                        print("  Format invalide. Ex : 5 5")
                        continue
                    c, r = int(parts[0])-1, int(parts[1])-1
                    if not (0 <= c <= 8 and 0 <= r <= 8):
                        print("  Coordonnees hors limites.")
                        continue
                    legal = state.get_legal_moves()
                    if (c, r) not in legal:
                        print("  Coup INVALIDE. Reessayez.")
                        print(f"  Coups legaux : {[(x+1,y+1) for x,y in legal]}")
                        continue
                    state.make_move((c, r))
                    print(f"  Adversaire joue : Colonne {c+1}, Ligne {r+1}")
                    break
                except ValueError:
                    print("  Entrez deux entiers. Ex : 5 5")

    # Statistiques
    print(f"\n{'='*50}")
    print("     STATISTIQUES DE TEMPS (Notre IA)")
    print(f"{'='*50}")
    if move_times:
        print(f"  Coups joues    : {len(move_times)}")
        print(f"  Temps cumule   : {sum(move_times):.3f}s")
        print(f"  Temps moyen    : {sum(move_times)/len(move_times):.3f}s")
        print(f"  Max            : {max(move_times):.3f}s")
        print(f"  Min            : {min(move_times):.3f}s")
        print(f"  Coups > 7s     : {sum(1 for t in move_times if t > 7)}")
        print("\n  Detail :")
        for i, t in enumerate(move_times):
            flag = f"  {RED}!!{RESET}" if t > 7.0 else ""
            print(f"    Coup {i+1:>2} : {t:.3f}s{flag}")
    else:
        print("  Aucun coup joue.")


if __name__ == "__main__":
    main()
