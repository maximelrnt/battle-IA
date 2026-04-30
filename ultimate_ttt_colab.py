"""
ultimate_ttt_colab.py
===================== 
Version Compétition (20/20)

DESCRIPTION :
Ce module contient l'IA à soumettre. Elle utilise un Minimax Alpha-Beta 
avec Iterative Deepening et des heuristiques de contrôle de zone.
"""

from __future__ import annotations
import math
import time
from typing import List, Optional, Tuple

# --- LOGIQUE DU JEU (Nécessaire pour que l'IA simule ses coups) ---

class TeamGameState:
    """Version optimisée de l'état pour les simulations de l'IA."""
    WIN_PATTERNS = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

    def __init__(self):
        self.board = [[0]*9 for _ in range(9)]
        self.global_board = [0]*9
        self.forced_subgrid = None
        self.current_player = 1 
        self._history = []

    def apply_move(self, col: int, row: int, player: int):
        sg_idx = (row // 3) * 3 + (col // 3)
        cell_idx = (row % 3) * 3 + (col % 3)
        self._history.append(((col, row), self.forced_subgrid, list(self.global_board), self.current_player))
        
        self.board[sg_idx][cell_idx] = player
        
        if self.global_board[sg_idx] == 0:
            b = self.board[sg_idx]
            for a, b_i, c in self.WIN_PATTERNS:
                if b[a] != 0 and b[a] == b[b_i] == b[c]:
                    self.global_board[sg_idx] = player
                    break
            if self.global_board[sg_idx] == 0 and all(x != 0 for x in b):
                self.global_board[sg_idx] = 2

        self.forced_subgrid = cell_idx if self.global_board[cell_idx] == 0 else None
        self.current_player = -player

    def undo_move(self):
        (col, row), fs, gb, p = self._history.pop()
        sg_idx = (row // 3) * 3 + (col // 3)
        self.board[sg_idx][(row % 3) * 3 + (col % 3)] = 0
        self.forced_subgrid, self.global_board, self.current_player = fs, gb, p

# --- MOTEUR DE DÉCISION (NOTRE IA) ---

class GroupAI:
    def __init__(self, my_player_id: int, time_limit: float = 2.8):
        self.me = my_player_id # 1 ou -1
        self.time_limit = time_limit
        self.state = TeamGameState()
        self.nodes = 0

    def update_with_opponent_move(self, col: int, row: int):
        """Met à jour notre état après le coup de l'autre équipe."""
        self.state.apply_move(col, row, -self.me)

    def compute_best_move(self) -> Tuple[int, int]:
        """Calcule et renvoie notre coup (col, row)."""
        start = time.time()
        self.nodes = 0
        best_m = None
        
        legal_moves = self._get_legal(self.state)
        # Fallback de sécurité
        if not legal_moves: return (0, 0)
        best_m = legal_moves[0]

        # Approfondissement itératif
        for depth in range(1, 15):
            if time.time() - start > self.time_limit * 0.9: break
            _, m = self._minimax(self.state, depth, -math.inf, math.inf, True, start)
            if m: best_m = m
        
        # On applique notre propre coup à notre état interne
        self.state.apply_move(best_m[0], best_m[1], self.me)
        return best_m

    def _minimax(self, state, depth, alpha, beta, maximizing, start):
        self.nodes += 1
        win = self._check_win(state)
        if win != 0 or depth == 0 or (self.nodes % 500 == 0 and time.time() - start > self.time_limit * 0.95):
            return self._evaluate(state), None

        moves = self._get_legal(state)
        # Move Ordering Pro (Centre > Coins)
        moves.sort(key=lambda m: (10 if m[0]%3==1 and m[1]%3==1 else 0), reverse=True)
        
        best_move = None
        if maximizing:
            v = -math.inf
            for m in moves:
                state.apply_move(m[0], m[1], self.me if maximizing else -self.me)
                val, _ = self._minimax(state, depth-1, alpha, beta, False, start)
                state.undo_move()
                if val > v: v, best_move = val, m
                alpha = max(alpha, v)
                if beta <= alpha: break
            return v, best_move
        else:
            v = math.inf
            for m in moves:
                state.apply_move(m[0], m[1], -self.me if maximizing else self.me)
                val, _ = self._minimax(state, depth-1, alpha, beta, True, start)
                state.undo_move()
                if val < v: v, best_move = val, m
                beta = min(beta, v)
                if beta <= alpha: break
            return v, best_move

    def _evaluate(self, state) -> float:
        win = self._check_win(state)
        if win == self.me: return 10**7
        if win == -self.me: return -10**7
        if win == 2: return -9999000 # Nul = Défaite
        
        score = 0
        for i, v in enumerate(state.global_board):
            w = 3 if i == 4 else 2 if i in [0,2,6,8] else 1
            if v == self.me: score += 1500 * w
            elif v == -self.me: score -= 1500 * w
        return score

    def _get_legal(self, state):
        if state.forced_subgrid is not None:
            m = self._in_sg(state, state.forced_subgrid)
            if m: return m
        res = []
        for i in range(9):
            if state.global_board[i] == 0: res.extend(self._in_sg(state, i))
        return res

    def _in_sg(self, state, sg):
        bc, br = (sg%3)*3, (sg//3)*3
        return [(bc+i%3, br+i//3) for i in range(9) if state.board[sg][i] == 0]

    def _check_win(self, state):
        gb = state.global_board
        for a, b, c in TeamGameState.WIN_PATTERNS:
            if gb[a] != 0 and gb[a] != 2 and gb[a] == gb[b] == gb[c]: return gb[a]
        return 2 if all(x != 0 for x in gb) else 0

# --- EXEMPLE D'UTILISATION (Pour toi) ---
# ia = GroupAI(my_player_id=1) # On est X
# coup = ia.compute_best_move() # Renvoie (col, row)
# ia.update_with_opponent_move(4, 4) # On informe l'IA du coup de l'autre équipe