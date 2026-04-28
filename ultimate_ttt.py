"""
ultimate_ttt.py
===============
Ultimate Tic Tac Toe — Implémentation complète (IA vs IA)
----------------------------------------------------------
Architecture :
    GameState   → logique pure du plateau (make/undo, coups légaux, victoire)
    Heuristics  → évaluation statique (nul = défaite, win-seeking)
    MinimaxAI   → Alpha-Beta + Move Ordering + Iterative Deepening
    GameRunner  → boucle CLI, affichage, mode IA vs IA

Convention interne :
    Joueur 1  =  X  (joue en premier si non précisé)
    Joueur -1 =  O
    Plateau   :  board[sub_row][sub_col][local_idx]
                 sub_row/col ∈ {0,1,2},  local_idx ∈ {0..8}
    Coordonnées CLI : colonne et ligne de 1 à 9 (converties en 0-indexé).
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Alias de types
# ─────────────────────────────────────────────────────────────────────────────

Move     = Tuple[int, int]          # (col, row) 0-indexés dans la grille 9×9
SubGrid  = Tuple[int, int]          # (sub_row, sub_col) 0-indexés dans la grille 3×3
SubBoard = List[int]                # 9 entiers : 0=vide, 1=X, -1=O
Board    = List[List[SubBoard]]     # 3×3 sous-grilles


# ─────────────────────────────────────────────────────────────────────────────
# GameState
# ─────────────────────────────────────────────────────────────────────────────

class GameState:
    """
    Représente l'état complet du jeu à un instant donné.

    Toute modification passe par make_move / undo_move pour permettre
    le backtracking sans copies profondes à chaque nœud du minimax.
    """

    # Les 8 combinaisons gagnantes sur un plateau 3×3 aplati (indices 0-8)
    WIN_PATTERNS: List[Tuple[int, int, int]] = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),   # lignes
        (0, 3, 6), (1, 4, 7), (2, 5, 8),   # colonnes
        (0, 4, 8), (2, 4, 6),               # diagonales
    ]

    def __init__(self) -> None:
        """Initialise un plateau vide."""
        # board[sr][sc] → liste de 9 cases (0, 1, -1)
        self.board: Board = [[[0] * 9 for _ in range(3)] for _ in range(3)]

        # Résultat de chaque sous-grille :
        #   0 = en cours, 1 = X gagne, -1 = O gagne, 2 = nulle
        self.global_board: List[List[int]] = [[0] * 3 for _ in range(3)]

        # Joueur courant : 1 (X) ou -1 (O)
        self.current_player: int = 1

        # Sous-grille où doit jouer le prochain joueur (None = libre)
        self.forced_subgrid: Optional[SubGrid] = None

        # Pile pour l'annulation de coups :
        #   (move, forced_subgrid_avant, snapshot_global_board, joueur_avant)
        self._history: list = []

    # ── Accès aux cases ────────────────────────────────────────────────────

    def get_cell(self, col: int, row: int) -> int:
        """
        Valeur d'une case en coordonnées globales 0-indexées.

        Parameters
        ----------
        col, row : int  Coordonnées globales (0-8).

        Returns
        -------
        int : 0 (vide), 1 (X), -1 (O).
        """
        local_idx = (row % 3) * 3 + (col % 3)
        return self.board[row // 3][col // 3][local_idx]

    def set_cell(self, col: int, row: int, value: int) -> None:
        """
        Écrit directement dans une case. Utilisé par make_move / undo_move.

        Parameters
        ----------
        col, row : int  Coordonnées globales (0-8).
        value    : int  0, 1 ou -1.
        """
        self.board[row // 3][col // 3][(row % 3) * 3 + (col % 3)] = value

    # ── Détection de victoire ──────────────────────────────────────────────

    def check_local_winner(self, sub_row: int, sub_col: int) -> int:
        """
        Résultat d'une sous-grille après le dernier coup joué dedans.

        Parameters
        ----------
        sub_row, sub_col : int  Position de la sous-grille (0-2).

        Returns
        -------
        int : 1 (X), -1 (O), 2 (nulle), 0 (en cours).
        """
        b = self.board[sub_row][sub_col]
        for a, c, d in self.WIN_PATTERNS:
            if b[a] != 0 and b[a] == b[c] == b[d]:
                return b[a]
        return 2 if all(x != 0 for x in b) else 0

    def check_global_winner(self) -> int:
        """
        Résultat de la partie globale.

        Returns
        -------
        int : 1 (X gagne), -1 (O gagne), 2 (nul), 0 (en cours).
        """
        flat = [self.global_board[r][c] for r in range(3) for c in range(3)]
        for a, b, c in self.WIN_PATTERNS:
            v = flat[a]
            if v not in (0, 2) and v == flat[b] == flat[c]:
                return v
        return 2 if all(x != 0 for x in flat) else 0

    def is_terminal(self) -> bool:
        """Retourne True si la partie est terminée."""
        return self.check_global_winner() != 0

    # ── Coups légaux ──────────────────────────────────────────────────────

    def get_legal_moves(self) -> List[Move]:
        """
        Liste des coups légaux pour le joueur courant.

        Règle : si forced_subgrid est disponible → contraint à jouer dedans.
        Sinon → toute case vide d'une sous-grille non terminée.

        Returns
        -------
        List[Move] : (col, row) 0-indexés.
        """
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
        """Cases vides d'une sous-grille en coordonnées globales."""
        moves: List[Move] = []
        for local_idx in range(9):
            if self.board[sub_row][sub_col][local_idx] == 0:
                lr, lc = divmod(local_idx, 3)
                moves.append((sub_col * 3 + lc, sub_row * 3 + lr))
        return moves

    def _is_subgrid_available(self, sub_row: int, sub_col: int) -> bool:
        """True si la sous-grille est non terminée (pas gagnée, pas nulle)."""
        return self.global_board[sub_row][sub_col] == 0

    # ── Application / annulation ───────────────────────────────────────────

    def make_move(self, move: Move) -> None:
        """
        Applique un coup sur le plateau (modifie l'état in-place).

        Effets :
            - Place le pion du joueur courant.
            - Met à jour global_board si la sous-grille change de statut.
            - Calcule forced_subgrid pour le prochain tour.
            - Passe la main à l'adversaire.
            - Empile un snapshot dans _history pour undo_move.

        Parameters
        ----------
        move : Move  (col, row) globaux 0-indexés.
        """
        col, row = move
        sr, sc = row // 3, col // 3
        local_idx = (row % 3) * 3 + (col % 3)

        # Snapshot léger pour undo (seul global_board change structurellement)
        prev_global = [r[:] for r in self.global_board]
        self._history.append((move, self.forced_subgrid, prev_global, self.current_player))

        # Pose du pion
        self.board[sr][sc][local_idx] = self.current_player

        # Mise à jour du statut de la sous-grille
        self.global_board[sr][sc] = self.check_local_winner(sr, sc)

        # Sous-grille forcée pour le prochain coup
        next_sr, next_sc = row % 3, col % 3
        self.forced_subgrid = (
            (next_sr, next_sc) if self._is_subgrid_available(next_sr, next_sc) else None
        )

        self.current_player = -self.current_player

    def undo_move(self) -> None:
        """
        Annule le dernier coup joué et restaure l'état précédent depuis _history.
        Complexité O(1) sur la partie plateau — seul le snapshot global_board est recopié.
        """
        move, forced_before, global_before, player_before = self._history.pop()
        col, row = move
        self.board[row // 3][col // 3][(row % 3) * 3 + (col % 3)] = 0
        self.global_board = global_before
        self.forced_subgrid = forced_before
        self.current_player = player_before

    def copy(self) -> "GameState":
        """
        Copie profonde de l'état. Utilisée uniquement hors du minimax
        (ex. : sauvegarder l'état avant l'affichage, tests).
        """
        new = GameState()
        new.board = [[sg[:] for sg in row] for row in self.board]
        new.global_board = [r[:] for r in self.global_board]
        new.current_player = self.current_player
        new.forced_subgrid = self.forced_subgrid
        return new

    def __repr__(self) -> str:
        """Représentation compacte pour le débogage."""
        lines: List[str] = []
        for row in range(9):
            if row > 0 and row % 3 == 0:
                lines.append("===+===+===")
            row_str = ""
            for col in range(9):
                if col > 0 and col % 3 == 0:
                    row_str += "‖"
                v = self.get_cell(col, row)
                row_str += " X" if v == 1 else (" O" if v == -1 else " .")
            lines.append(row_str)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Heuristics
# ─────────────────────────────────────────────────────────────────────────────

class Heuristics:
    """
    Évaluation statique du plateau pour un joueur donné.

    Philosophie :
        - Victoire  →  +WIN_SCORE  (très grand)
        - Nul       →  -WIN_SCORE + 1  (quasi-défaite : les deux IA jouent à fond)
        - Défaite   →  -WIN_SCORE
        - Intermédiaire : pondération fine des structures de jeu.

    Toutes les constantes sont regroupées ici pour faciliter le tuning.
    """

    WIN_SCORE:  int = 1_000_000
    # Le nul vaut presque autant qu'une défaite → force l'IA à chercher la victoire
    DRAW_SCORE: int = -(WIN_SCORE - 1)

    # Pondérations heuristiques
    W_LOCAL_WIN:       float = 3_000   # Sous-grille gagnée sur le plateau global
    W_NEAR_GLOBAL_WIN: float = 1_200   # 2 sous-grilles gagnées sur une même ligne globale
    W_CENTER_GLOBAL:   float = 400     # Contrôle de la sous-grille centrale
    W_CORNER_GLOBAL:   float = 150     # Sous-grille coin gagnée
    W_CENTER_LOCAL:    float = 90      # Centre d'une sous-grille locale
    W_CORNER_LOCAL:    float = 45      # Coin d'une sous-grille locale
    W_LINE_TWO:        float = 70      # 2 pions + 1 vide dans une ligne locale
    W_LINE_ONE:        float = 15      # 1 pion + 2 vides dans une ligne locale
    W_SEND_ACTIVE:     float = 80      # Pénalité : envoyer l'adversaire sur une grille active avantageuse
    W_SEND_FINISHED:   float = 60      # Bonus : envoyer l'adversaire sur une grille terminée

    @staticmethod
    def evaluate(state: GameState, maximizing_player: int) -> float:
        """
        Évaluation statique complète du plateau.

        Parameters
        ----------
        state             : GameState   État courant.
        maximizing_player : int         Joueur dont on maximise (1 ou -1).

        Returns
        -------
        float : Score (positif = avantageux pour maximizing_player).
        """
        winner = state.check_global_winner()
        if winner == maximizing_player:
            return float(Heuristics.WIN_SCORE)
        if winner == -maximizing_player:
            return float(-Heuristics.WIN_SCORE)
        if winner == 2:                          # Nul = quasi-défaite
            return float(Heuristics.DRAW_SCORE)

        score = 0.0
        score += Heuristics._score_global_board(state, maximizing_player)
        score += Heuristics._score_local_boards(state, maximizing_player)
        score += Heuristics._score_sending(state, maximizing_player)
        return score

    # ── Composantes d'évaluation ──────────────────────────────────────────

    @staticmethod
    def _score_global_board(state: GameState, player: int) -> float:
        """
        Évalue la grille globale 3×3 des sous-grilles gagnées.

        Prend en compte :
            - Sous-grilles remportées / perdues.
            - Lignes quasi-gagnées (2 + 1 libre) sur la grille globale.
            - Contrôle du centre et des coins de la grille globale.
        """
        score = 0.0
        flat = [state.global_board[r][c] for r in range(3) for c in range(3)]
        corners = (0, 2, 6, 8)

        for idx, v in enumerate(flat):
            if v == player:
                score += Heuristics.W_LOCAL_WIN
                if idx == 4:
                    score += Heuristics.W_CENTER_GLOBAL
                if idx in corners:
                    score += Heuristics.W_CORNER_GLOBAL
            elif v == -player:
                score -= Heuristics.W_LOCAL_WIN
                if idx == 4:
                    score -= Heuristics.W_CENTER_GLOBAL
                if idx in corners:
                    score -= Heuristics.W_CORNER_GLOBAL

        # Lignes quasi-gagnées sur la grille globale
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
        """
        Évalue chaque sous-grille locale encore en jeu.

        Prend en compte :
            - Cases centre et coins de chaque sous-grille.
            - Lignes ouvertes à 1 et 2 pions.
        """
        score = 0.0
        corners = (0, 2, 6, 8)

        for sr in range(3):
            for sc in range(3):
                if state.global_board[sr][sc] != 0:
                    continue
                b = state.board[sr][sc]

                # Centre de la sous-grille
                score += Heuristics.W_CENTER_LOCAL * (
                    (1 if b[4] == player else 0) - (1 if b[4] == -player else 0)
                )

                # Coins de la sous-grille
                for idx in corners:
                    score += Heuristics.W_CORNER_LOCAL * (
                        (1 if b[idx] == player else 0) - (1 if b[idx] == -player else 0)
                    )

                # Lignes locales
                for a, bi, c in GameState.WIN_PATTERNS:
                    line = (b[a], b[bi], b[c])
                    p_cnt = line.count(player)
                    o_cnt = line.count(-player)
                    empty = line.count(0)
                    if o_cnt == 0:
                        if p_cnt == 2 and empty == 1:
                            score += Heuristics.W_LINE_TWO
                        elif p_cnt == 1 and empty == 2:
                            score += Heuristics.W_LINE_ONE
                    if p_cnt == 0:
                        if o_cnt == 2 and empty == 1:
                            score -= Heuristics.W_LINE_TWO
                        elif o_cnt == 1 and empty == 2:
                            score -= Heuristics.W_LINE_ONE

        return score

    @staticmethod
    def _score_sending(state: GameState, player: int) -> float:
        """
        Évalue l'impact de la sous-grille vers laquelle le joueur courant est envoyé.

        - Envoyer l'adversaire vers une grille terminée = bon (il joue librement
          mais ne peut plus y gagner de sous-grille).
        - Envoyer l'adversaire vers une grille active avec menaces = mauvais.
        """
        score = 0.0
        fs = state.forced_subgrid
        if fs is None:
            return 0.0

        sr, sc = fs
        gv = state.global_board[sr][sc]

        # Grille terminée → l'adversaire joue librement mais sans enjeu local
        if gv != 0:
            bonus = Heuristics.W_SEND_FINISHED
            score += bonus if state.current_player == -player else -bonus
            return score

        # Grille active : combien de menaces immédiates pour qui va y jouer ?
        b = state.board[sr][sc]
        next_player = state.current_player   # celui qui va jouer dans cette grille
        threat_count = 0
        for a, bi, c in GameState.WIN_PATTERNS:
            line = (b[a], b[bi], b[c])
            p_line = line.count(next_player)
            o_line = line.count(-next_player)
            if o_line == 0 and p_line == 2:
                threat_count += 1

        penalty = threat_count * Heuristics.W_SEND_ACTIVE
        # Si next_player == -player (adversaire), c'est mauvais pour player
        score += -penalty if next_player == -player else penalty
        return score

    @staticmethod
    def _count_open_lines(subboard: SubBoard, player: int) -> int:
        """
        Nombre de lignes encore gagnables pour `player` dans une sous-grille
        (aucun pion adverse sur la ligne).
        """
        return sum(
            1 for a, b, c in GameState.WIN_PATTERNS
            if -player not in (subboard[a], subboard[b], subboard[c])
            and player in (subboard[a], subboard[b], subboard[c])
        )


# ─────────────────────────────────────────────────────────────────────────────
# MinimaxAI
# ─────────────────────────────────────────────────────────────────────────────

class MinimaxAI:
    """
    IA basée sur Minimax avec élagage Alpha-Beta.

    Fonctionnalités :
        - Iterative Deepening : explore depth=1, 2, 3… jusqu'à la limite de temps.
          Le meilleur coup de la dernière profondeur complète est retourné.
        - Move Ordering : les coups les plus prometteurs sont explorés en premier
          (coups gagnants, centre, coins, envoi sur grille terminée).
        - make / undo : aucune copie profonde pendant la recherche.
    """

    # Marge de sécurité sur le temps (évite le dépassement sur Colab)
    _TIME_MARGIN: float = 0.97

    def __init__(
        self,
        player: int = -1,
        time_limit: float = 3.0,
        max_depth: int = 15,
    ) -> None:
        """
        Parameters
        ----------
        player     : int    Joueur IA (1 = X, -1 = O). Flexible dès l'init.
        time_limit : float  Budget temps en secondes par coup.
        max_depth  : int    Plafond absolu de profondeur (sécurité).
        """
        self.player:     int   = player
        self.time_limit: float = time_limit
        self.max_depth:  int   = max_depth

        # Statistiques (réinitialisées à chaque coup)
        self.nodes_explored:    int   = 0
        self.depth_reached:     int   = 0
        self._start_time:       float = 0.0
        self._time_exceeded:    bool  = False
        self._best_move_iter:   Optional[Move] = None

    # ── Interface publique ────────────────────────────────────────────────

    def choose_move(self, state: GameState) -> Move:
        """
        Sélectionne le meilleur coup via Iterative Deepening Alpha-Beta.

        Retourne toujours un coup valide même si le temps est immédiatement
        dépassé (fallback sur le premier coup légal).

        Parameters
        ----------
        state : GameState  État courant (non modifié en sortie).

        Returns
        -------
        Move : (col, row) 0-indexé.
        """
        self._reset_stats()
        legal_moves = state.get_legal_moves()

        if not legal_moves:
            raise RuntimeError("Aucun coup légal disponible — état terminal non détecté.")
        if len(legal_moves) == 1:
            return legal_moves[0]

        # Fallback : premier coup après move ordering
        best_move: Move = self._order_moves(legal_moves, state)[0]

        for depth in range(1, self.max_depth + 1):
            if self._is_time_up():
                break

            self._time_exceeded = False
            self._best_move_iter = None

            ordered = self._order_moves(legal_moves, state)
            local_best_score = -math.inf
            local_best_move  = ordered[0]

            for move in ordered:
                if self._is_time_up():
                    self._time_exceeded = True
                    break
                state.make_move(move)
                score = self._alpha_beta(state, depth - 1, -math.inf, math.inf, False)
                state.undo_move()

                if score > local_best_score:
                    local_best_score = score
                    local_best_move  = move

                # Victoire assurée → inutile d'aller plus loin
                if local_best_score >= Heuristics.WIN_SCORE:
                    break

            # On ne valide la profondeur que si la recherche est complète
            if not self._time_exceeded:
                best_move        = local_best_move
                self.depth_reached = depth

            if local_best_score >= Heuristics.WIN_SCORE:
                break

        elapsed = time.time() - self._start_time
        sym = "X" if self.player == 1 else "O"
        print(
            f"  [IA {sym}] profondeur={self.depth_reached} | "
            f"nœuds={self.nodes_explored:,} | temps={elapsed:.3f}s"
        )
        return best_move

    # ── Algorithme Alpha-Beta ─────────────────────────────────────────────

    def _alpha_beta(
        self,
        state:      GameState,
        depth:      int,
        alpha:      float,
        beta:       float,
        maximizing: bool,
    ) -> float:
        """
        Minimax récursif avec élagage Alpha-Beta.

        Le joueur MAX est toujours self.player ; MIN est son adversaire.
        L'évaluation est toujours du point de vue de self.player.

        Parameters
        ----------
        state      : GameState  État courant (modifié via make/undo).
        depth      : int        Profondeur restante.
        alpha      : float      Meilleur garanti pour MAX.
        beta       : float      Meilleur garanti pour MIN.
        maximizing : bool       True si c'est le tour de self.player.

        Returns
        -------
        float : Score minimax.
        """
        self.nodes_explored += 1

        # ── Cas de base ──
        if state.is_terminal() or depth == 0:
            return Heuristics.evaluate(state, self.player)
        if self._is_time_up():
            self._time_exceeded = True
            return Heuristics.evaluate(state, self.player)

        legal_moves = state.get_legal_moves()
        if not legal_moves:                     # sécurité
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
                alpha    = max(alpha, ev)
                if beta <= alpha:
                    break               # Coupure β
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
                beta     = min(beta, ev)
                if beta <= alpha:
                    break               # Coupure α
            return min_eval

    # ── Move Ordering ─────────────────────────────────────────────────────

    def _order_moves(self, moves: List[Move], state: GameState) -> List[Move]:
        """
        Trie les coups du plus prometteur au moins prometteur.

        Améliore drastiquement les coupures alpha-beta en explorant
        les branches les plus intéressantes en premier.

        Parameters
        ----------
        moves : List[Move]  Coups légaux non triés.
        state : GameState   État courant (lecture seule).

        Returns
        -------
        List[Move] : Coups triés (score décroissant).
        """
        return sorted(moves, key=lambda m: self._move_priority(m, state), reverse=True)

    def _move_priority(self, move: Move, state: GameState) -> float:
        """
        Score de priorité d'un coup pour le Move Ordering.

        Critères (du plus fort au plus faible) :
            1. Le coup gagne la sous-grille locale (+500).
            2. Le coup envoie l'adversaire sur une grille terminée (+120).
            3. Centre de la sous-grille locale (+80).
            4. Sous-grille centrale de la grille globale (+70).
            5. Coin de la sous-grille locale (+40).
            6. Coup bloquant une victoire locale adverse (+300).

        Parameters
        ----------
        move  : Move
        state : GameState

        Returns
        -------
        float
        """
        col, row = move
        sub_row, sub_col = row // 3, col // 3
        local_idx = (row % 3) * 3 + (col % 3)

        priority  = 0.0
        b_copy    = state.board[sub_row][sub_col][:]
        b_copy[local_idx] = state.current_player

        # 1. Ce coup gagne la sous-grille ?
        for a, bi, c in GameState.WIN_PATTERNS:
            if b_copy[a] != 0 and b_copy[a] == b_copy[bi] == b_copy[c]:
                priority += 500.0
                break

        # 6. Ce coup bloque une victoire adverse ?
        b_opp = state.board[sub_row][sub_col][:]
        b_opp[local_idx] = -state.current_player
        for a, bi, c in GameState.WIN_PATTERNS:
            if b_opp[a] != 0 and b_opp[a] == b_opp[bi] == b_opp[c]:
                priority += 300.0
                break

        # 2. Envoie vers grille terminée ?
        next_sr, next_sc = row % 3, col % 3
        if state.global_board[next_sr][next_sc] != 0:
            priority += 120.0

        # 3. Centre de la sous-grille locale
        if local_idx == 4:
            priority += 80.0
        elif local_idx in (0, 2, 6, 8):        # Coin
            priority += 40.0

        # 4. Sous-grille centrale de la grille globale
        if sub_row == 1 and sub_col == 1:
            priority += 70.0

        return priority

    # ── Utilitaires ───────────────────────────────────────────────────────

    def _is_time_up(self) -> bool:
        """Vrai si le budget temps est épuisé (avec marge de sécurité)."""
        return (time.time() - self._start_time) >= self.time_limit * self._TIME_MARGIN

    def _reset_stats(self) -> None:
        """Réinitialise les compteurs avant chaque nouveau coup."""
        self.nodes_explored  = 0
        self.depth_reached   = 0
        self._time_exceeded  = False
        self._best_move_iter = None
        self._start_time     = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# GameRunner
# ─────────────────────────────────────────────────────────────────────────────

class GameRunner:
    """
    Orchestre la boucle de jeu en mode IA vs IA.

    L'affichage texte distingue clairement les sous-grilles et indique
    la sous-grille forcée ainsi que le statut des grilles terminées.
    """

    # Symboles utilisés à l'affichage
    _SYMBOLS = {1: "X", -1: "O", 0: "."}
    _GLOBAL_STATUS = {1: "[X]", -1: "[O]", 2: "[=]"}

    def __init__(
        self,
        player_one: int   = 1,
        time_limit: float = 3.0,
    ) -> None:
        """
        Parameters
        ----------
        player_one : int    Joueur qui commence (1=X, -1=O).
        time_limit : float  Budget temps de chaque IA en secondes.
        """
        self.state: GameState = GameState()
        self.state.current_player = player_one

        # Deux IA indépendantes — chacune connaît son identité
        self.ai_X: MinimaxAI = MinimaxAI(player=1,  time_limit=time_limit)
        self.ai_O: MinimaxAI = MinimaxAI(player=-1, time_limit=time_limit)

        self._time_limit = time_limit
        self._move_count = 0

    # ── Boucle de jeu ─────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Boucle principale du jeu IA vs IA.

        Séquence par tour :
            1. Afficher le plateau.
            2. L'IA du joueur courant choisit son coup.
            3. Appliquer le coup.
            4. Vérifier la fin de partie.
        """
        print("\n" + "═" * 45)
        print("   ULTIMATE TIC TAC TOE  —  IA vs IA")
        print("═" * 45)

        while not self.state.is_terminal():
            self.display_board()
            current = self.state.current_player
            sym     = self._SYMBOLS[current]
            ai      = self.ai_X if current == 1 else self.ai_O

            print(f"\n▶  Tour #{self._move_count + 1} — IA {sym} réfléchit…")
            move = ai.choose_move(self.state)
            col_display = move[0] + 1
            row_display = move[1] + 1
            print(f"   → Coup joué : colonne {col_display}, ligne {row_display}")

            self.state.make_move(move)
            self._move_count += 1

        self.display_board()
        winner = self.state.check_global_winner()
        self._announce_result(winner)

    # ── Affichage ─────────────────────────────────────────────────────────

    def display_board(self) -> None:
        """
        Affiche le plateau 9×9 avec :
            - Séparateurs épais entre sous-grilles.
            - 'X', 'O', '.' pour les cases vides.
            - Statut résumé de chaque sous-grille terminée.
            - Indication de la sous-grille forcée.
        """
        fs = self.state.forced_subgrid
        print()

        # En-tête coordonnées colonnes (1-9)
        print("     " + "  ".join(str(c + 1) for c in range(9)))
        print("    " + "─" * 29)

        for row in range(9):
            if row > 0 and row % 3 == 0:
                # Séparateur entre sous-grilles horizontales
                print("    " + "═" * 29)

            row_parts: List[str] = []
            for sg_col in range(3):
                sub_row = row // 3
                sub_col = sg_col
                cells: List[str] = []

                if self.state.global_board[sub_row][sg_col] != 0:
                    # Sous-grille terminée : affichage symbolique sur la ligne centrale
                    local_row_in_sg = row % 3
                    status = self._GLOBAL_STATUS[self.state.global_board[sub_row][sg_col]]
                    if local_row_in_sg == 1:
                        cells.append(f" {status} ")   # ligne centrale
                    else:
                        cells.append("       ")
                else:
                    for lc in range(3):
                        global_col = sg_col * 3 + lc
                        v = self.state.get_cell(global_col, row)
                        cells.append(f" {self._SYMBOLS[v]} ")

                row_parts.append("".join(cells))

            forced_markers = []
            for sg_col in range(3):
                sub_row = row // 3
                marker = "◀" if (fs is not None and fs == (sub_row, sg_col)) else " "
                forced_markers.append(marker)

            line = f" {row + 1}  " + " ‖".join(row_parts)
            print(line)

        if fs is not None:
            sr, sc = fs
            print(f"\n  ↳ Jouer dans la sous-grille ligne {sr + 1}, colonne {sc + 1}")
        else:
            print("\n  ↳ Libre de jouer dans n'importe quelle sous-grille disponible")

    # ── Résultat ──────────────────────────────────────────────────────────

    def _announce_result(self, winner: int) -> None:
        """
        Affiche le message de fin de partie.

        Parameters
        ----------
        winner : int  1 (X gagne), -1 (O gagne), 2 (match nul).
        """
        print("\n" + "═" * 45)
        if winner == 2:
            print("  MATCH NUL — victoire de personne !")
        else:
            sym = self._SYMBOLS[winner]
            print(f"  🏆  L'IA {sym} GAGNE la partie en {self._move_count} coups !")
        print("═" * 45 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # X toujours en premier, budget de 3 secondes par coup
    runner = GameRunner(player_one=1, time_limit=3.0)
    runner.run()
