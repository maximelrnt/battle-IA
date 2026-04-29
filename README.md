# 🚀 Battle-IA : Ultimate Tic-Tac-Toe AI

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Ce projet est une implémentation haute performance d'une intelligence artificielle pour le jeu **Ultimate Tic-Tac-Toe**, développée dans le cadre du cours *Fondements de l'IA* à l'ESILV.

---

## 🎮 Le Jeu : Ultimate Tic-Tac-Toe

L'Ultimate Tic-Tac-Toe est une variante complexe du Morpion classique. Le plateau est composé de **9 sous-grilles** de 3×3. Pour gagner la partie, un joueur doit aligner trois sous-grilles gagnées. La subtilité réside dans le fait que le coup joué par l'adversaire détermine la sous-grille dans laquelle vous devez jouer votre prochain coup.

## 🧠 L'Intelligence Artificielle

Notre IA repose sur des algorithmes de théorie des jeux éprouvés, optimisés pour la compétition.

### ⚡ Algorithmes de Recherche
- **Minimax avec Élagage Alpha-Béta** : Réduit drastiquement l'espace de recherche en ignorant les branches qui ne peuvent pas influencer la décision finale.
- **Iterative Deepening (Approfondissement Itératif)** : Permet à l'IA d'explorer le jeu de plus en plus profondément tout en respectant une contrainte de temps stricte (ex: 3 secondes par coup).
- **Move Ordering (Ordonnancement des coups)** : Les coups les plus prometteurs (centre, coins, blocages) sont explorés en premier pour maximiser l'efficacité de l'élagage Alpha-Béta.

### 📊 Système d'Heuristiques
L'IA évalue la qualité d'un plateau à l'aide d'une fonction d'évaluation pondérée :
- **Contrôle Global** : Forte priorité sur le gain de sous-grilles locales.
- **Positionnement Stratégique** : Bonus pour le contrôle du centre et des coins (locaux et globaux).
- **Menaces et Blocages** : Identification des alignements de 2 pions pour finir une grille ou bloquer l'adversaire.
- **Stratégie "Win-Seeking"** : L'IA considère un match nul comme une défaite (`DRAW_SCORE ≈ -WIN_SCORE`), ce qui la pousse à prendre des risques calculés pour arracher la victoire plutôt que de subir un blocage.

---

## 📁 Structure du Projet

- 📂 `ultimate_ttt.py` : Version complète avec moteur de jeu CLI, affichage détaillé et mode IA vs IA pour le test des heuristiques.
- 📂 `ultimate_ttt_colab.py` : Version allégée et optimisée pour la soumission en compétition (Google Colab / Tournoi).
- 📂 `IA-5.pdf` : Documentation ou sujet relatif au projet.

---

## 🚀 Installation et Utilisation

### Prérequis
- Python 3.8 ou supérieur.

### Lancer une démonstration
Pour voir deux instances de notre IA s'affronter localement :
```bash
python ultimate_ttt.py
```

---

## 🛠️ Détails Techniques

### Gestion du Temps
L'IA utilise une marge de sécurité (`TIME_MARGIN = 0.97`) pour s'assurer de renvoyer un coup avant la limite de temps, même en cas de calculs intensifs sur les derniers niveaux de profondeur.

### Backtracking Optimisé
Le moteur de jeu utilise les méthodes `make_move` et `undo_move` pour modifier l'état du plateau *in-place*. Cela évite des copies profondes coûteuses en mémoire et en temps CPU à chaque nœud de l'arbre Minimax.

---

## 👨‍💻 Auteurs
- **Maxime Laurent** - *Étudiant à l'ESILV*
- **Louis** - *Étudiant à l'ESILV*

---
*Projet réalisé dans le cadre de l'année 3 - ESILV.*