"""
projetv1.py — Interface de combat IA (Ultimate Tic-Tac-Toe)
============================================================
Utilise le moteur MinimaxAI de ultimate_ttt.py (timeout propre, heuristique riche).
Permet de jouer contre une autre IA humain-interposé.
Contrainte stricte : max 7 secondes par coup.
"""

import time
from ultimate_ttt import GameState, MinimaxAI

# ─────────────────────────────────────────────────────────────────────────────
# Affichage du plateau
# ─────────────────────────────────────────────────────────────────────────────

SYMBOLS = {0: '.', 1: 'X', -1: 'O'}

def print_board(state: GameState) -> None:
    """Affiche le plateau 9x9 avec séparateurs visuels entre sous-grilles."""
    
    # En-tête colonnes (1-9 selon le sujet)
    print("\n     1  2  3   4  5  6   7  8  9")
    print("   +----------+---------+---------+")
    
    for row in range(9):
        if row > 0 and row % 3 == 0:
            print("   +----------+---------+---------+")
        
        row_str = f" {row + 1} |"
        for col in range(9):
            if col > 0 and col % 3 == 0:
                row_str += " |"
            cell = state.get_cell(col, row)
            row_str += f" {SYMBOLS[cell]} "
        row_str += " |"
        print(row_str)
    
    print("   +----------+---------+---------+")
    
    # État des sous-grilles globales
    print("\n  [Grilles globales]")
    global_syms = {0: '·', 1: 'X', -1: 'O', 2: '='}
    for r in range(3):
        vals = [global_syms[state.global_board[r][c]] for c in range(3)]
        print(f"   {vals[0]}  {vals[1]}  {vals[2]}")
    
    # Indication sous-grille forcée
    if state.forced_subgrid is not None:
        sr, sc = state.forced_subgrid
        print(f"\n  => Grille forcée : ligne {sr+1}, colonne {sc+1}")
    else:
        print("\n  => Jeu libre (n'importe quelle grille disponible)")


# ─────────────────────────────────────────────────────────────────────────────
# Boucle principale
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("   BATTLE IA : ULTIMATE TIC-TAC-TOE")
    print("=" * 50)
    
    # --- Choix de qui commence ---
    while True:
        starter = input("\nQui commence ? (1 = Nous, 2 = Eux) : ").strip()
        if starter in ['1', '2']:
            break
        print("Erreur : Veuillez entrer 1 ou 2.")
    
    # Notre IA est toujours un joueur (1 ou -1)
    # Le joueur 1 (X) commence toujours dans le standard du jeu
    my_id = 1 if starter == '1' else -1
    opponent_id = -my_id
    
    print(f"\nConfiguration : Notre IA est {'X (joue en premier)' if my_id == 1 else 'O (joue en second)'}.")
    print("Temps de réflexion max : 7 secondes.")
    
    # Initialisation du moteur
    state = GameState()
    
    # L'IA utilise le moteur de ultimate_ttt.py avec timeout strict à 6.8s
    # (marge de 0.2s pour la sécurité)
    ai = MinimaxAI(player=my_id, time_limit=6.8, max_depth=15)
    
    move_times = []
    move_count = 0
    
    while True:
        print_board(state)
        
        # Vérifier fin de partie
        winner = state.check_global_winner()
        if winner != 0:
            print("\n" + "=" * 50)
            print("          FIN DE LA PARTIE")
            print("=" * 50)
            if winner == my_id:
                print("   NOTRE IA A GAGNÉ ! ")
            elif winner == opponent_id:
                print("  L'ADVERSAIRE A GAGNÉ... ")
            else:
                print("   MATCH NUL !")
            break
        
        current = state.current_player
        move_count += 1
        
        if current == my_id:
            # --- TOUR DE NOTRE IA ---
            print(f"\n  [Tour #{move_count}] NOTRE IA RÉFLÉCHIT...")
            start_time = time.time()
            
            # L'IA calcule son coup (timeout géré en interne)
            col, row = ai.choose_move(state)
            
            end_time = time.time()
            duration = end_time - start_time
            move_times.append(duration)
            
            # Afficher le coup (en 1-indexé selon le sujet)
            print(f"   Notre IA joue : Colonne {col + 1}, Ligne {row + 1}")
            print(f"    Temps : {duration:.3f}s")
            
            if duration > 7.0:
                print(f"   ATTENTION : dépassement du temps ({duration:.1f}s > 7s)")
            
            # Appliquer le coup
            state.make_move((col, row))
            
        else:
            # --- TOUR DE L'ADVERSAIRE ---
            print(f"\n  [Tour #{move_count}] TOUR DE L'ADVERSAIRE")
            
            while True:
                try:
                    move_str = input("  Entrez le coup adverse (colonne ligne, de 1 à 9) : ")
                    parts = move_str.strip().split()
                    if len(parts) != 2:
                        print("  Format invalide. Exemple : 5 5")
                        continue
                    
                    # Conversion 1-indexé → 0-indexé
                    col_input, row_input = int(parts[0]) - 1, int(parts[1]) - 1
                    
                    if not (0 <= col_input <= 8 and 0 <= row_input <= 8):
                        print("  Coordonnées hors limites (1 à 9).")
                        continue
                    
                    legal = state.get_legal_moves()
                    if (col_input, row_input) not in legal:
                        print("   Coup INVALIDE selon les règles. Réessayez.")
                        print(f"     Coups légaux : {[(c+1, r+1) for c, r in legal]}")
                        continue
                    
                    state.make_move((col_input, row_input))
                    print(f"  Adversaire joue : Colonne {col_input + 1}, Ligne {row_input + 1}")
                    break
                    
                except ValueError:
                    print("  Entrez deux nombres entiers. Exemple : 5 5")
    
    # --- STATISTIQUES ---
    print("\n" + "=" * 50)
    print("       STATISTIQUES DE TEMPS (Notre IA)")
    print("=" * 50)
    if move_times:
        print(f"  Nombre de coups joués  : {len(move_times)}")
        print(f"  Temps total cumulé     : {sum(move_times):.3f}s")
        print(f"  Temps moyen par coup   : {sum(move_times)/len(move_times):.3f}s")
        print(f"  Temps le plus long     : {max(move_times):.3f}s")
        print(f"  Temps le plus court    : {min(move_times):.3f}s")
        print(f"  Coups > 5s             : {sum(1 for t in move_times if t > 5)}")
        print(f"  Coups > 7s (VIOLATION) : {sum(1 for t in move_times if t > 7)}")
        
        print("\n  Détail par coup :")
        for i, t in enumerate(move_times):
            flag = " " if t > 7.0 else ""
            print(f"    Coup {i+1:>2} : {t:.3f}s{flag}")
    else:
        print("  Aucun coup joué par notre IA.")


if __name__ == "__main__":
    main()
