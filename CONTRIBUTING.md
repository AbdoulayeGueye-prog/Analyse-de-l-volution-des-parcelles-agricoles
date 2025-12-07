# Guide de contribution

Bienvenue dans le projet **Analyse de l'évolution des parcelles agricoles**.  
Nous sommes trois membres : **Dieumbe**, **Abdoulaye**, et **Dabakh**.  
Ce guide explique pas à pas comment travailler avec GitHub, même si vous êtes débutants.

---

## Les branches

- **main** : version stable, toujours fonctionnelle. Faut pas toucher svp
- **dev** : branche de développement commune.  
- **feature-dieumbe**, **feature-abdoulaye**, **feature-dabakh** : branches individuelles pour chaque membre.  

 Chacun travaille sur **sa branche**, puis envoie ses changements vers `dev`.  
 Seul **Dieumbe** est responsable des Pull Requests et des fusions vers `dev` et `main`.

---

## Étapes pour contribuer

### 1. Vérifier la branche active
```bash
git branch

### Comment activer votre branche personnelle 
```bash
git checkout feature-nom

## Sauvegerde des changementd
git add .
git commit -m "feat: description claire de ce que vous avez fait"

# envoi ver le github 
git push origin feature-nom

# Deconnecter de votre branche 

git checkout nom_brance


# Shema flux du travail

feature-dieumbe   ─┐
feature-abdoulaye ─┼──> dev ───> main
feature-dabakh    ─┘

Dieumbe valide et fusionne les Pull Requests

###Les regles de lq collab 

- Toujours travailler sur une branche feature-*.
- Ne jamais pousser directement sur main.
- Documenter chaque fonction et chaque test.
- Utiliser des commits clairs et concis.
- Respecter les assignations du tableau Suivi des Sprints.


