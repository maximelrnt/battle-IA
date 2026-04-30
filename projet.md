# Battle IA : Ultimate Tic-Tac-Toe

## Objectif
Créer un script interactif permettant de faire affronter notre IA (`GroupAI`) contre une autre IA lors d'un affrontement direct, en entrant les coups de l'adversaire manuellement.

## Spécifications de l'Interface (`projetv1.py`)

1. **Initialisation** : 
   - Demander à l'utilisateur qui commence le match (1 = Nous, ou 2 = Eux).
   
2. **Déroulement de la partie (Boucle de jeu)** :
   - À chaque tour, **afficher le plateau complet** de manière structurée pour bien visualiser l'état de l'Ultimate Tic-Tac-Toe.
   - Indiquer visuellement si une sous-grille est forcée ou si c'est un jeu libre.
   - **Tour de l'Adversaire** : Demander son coup via les coordonnées "colonne ligne" (séparées par un espace). Le script s'assure de vérifier la validité du coup et recommence en cas d'erreur.
   - **Tour de notre IA** : L'IA calcule son coup automatiquement et affiche les coordonnées du coup qu'elle a décidé de jouer ("colonne, ligne").

3. **Contraintes de temps** :
   - L'IA doit réfléchir pendant **7 secondes maximum** par coup (réglé de manière sécurisée en interne).
   - Le script doit chronométrer l'IA lors de son calcul (`compute_best_move`) et afficher ce temps en fin de tour.

4. **Fin de partie & Statistiques** :
   - Détecter et annoncer la fin de partie (Victoire de l'IA, Défaite, ou Match Nul).
   - Compiler et afficher des statistiques sur le temps de réflexion de notre IA une fois le jeu terminé : 
     - Nombre total de coups joués par notre IA.
     - Temps total cumulé.
     - Temps moyen de réflexion par coup.
     - Temps maximum (le plus long) et minimum (le plus court) de réflexion sur un coup.

## Fichiers
- `ultimate_ttt_colab.py` : Module qui contient la classe `GroupAI`, l'algorithme Minimax Alpha-Beta, et la logique interne du jeu.
- `projetv1.py` : Le programme principal qui exécute l'interface et gère l'arbitrage.
- `projet.md` : Les consignes et explications du projet (ce document).
