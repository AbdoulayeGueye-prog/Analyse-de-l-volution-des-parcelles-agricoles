# Analyse automatisée de l’évolution de l’usage agricole des sols (Plugin QGIS)

## 1. Objectifs du projet

Ce projet vise à développer un **plugin QGIS** permettant d’analyser automatiquement l’évolution des **parcelles agricoles** entre deux dates distinctes : **T1** (année de référence) et **T2** (année d’analyse).  
L’objectif principal est de détecter et de caractériser les changements dans l’usage du sol agricole, à partir de deux couches polygonales de parcelles.

Plus précisément, le plugin permet de :

- Identifier les **parcelles conservées**, **disparues** ou **nouvelles**.
- Estimer les **variations de surface** entre T1 et T2 (augmentation, diminution ou stabilité).
- Calculer automatiquement :  
  - la surface à T1 (`A_T1`)  
  - la surface équivalente à T2 (`A_T2`)  
  - la différence de surface (`ΔA = A_T2 − A_T1`)  
  - la variation relative (`Δ%`)  
- Classer les parcelles selon un **seuil (%)** défini par l’utilisateur.  
- Générer une **couche de sortie** annotée, exportable dans le format souhaité.

Le plugin a été conçu pour être simple, reproductible et performant, en s’intégrant entièrement dans l’interface QGIS.

---

## 2. Données utilisées

Le plugin fonctionne exclusivement avec des **polygones** représentant des parcelles agricoles, chargés dans QGIS.Les données utilisées pour le test proviennent **BDPPAD** (Base de données des parcelles et productions agricoles déclarées).La Base de données des parcelles et productions agricoles déclarées (BDPPAD) est constituée de polygones en format vectoriel représentant le contour des parcelles agricoles qui ont été associées aux dossiers des clients de La Financière agricole du Québec (FADQ) depuis 2003. Les parcelles sont conservées d’année en année pour constituer une banque de parcelles couvrant le plus de territoire possible, que le client associé soit actif ou non. Pour chaque année d’assurance, une production agricole est associée aux parcelles que les clients actifs déclarent cultiver.
### Table : Données 
| Élément | Description |
|--------|-------------|
| Source | BDPPAD — Gouvernement du Québec |http://www.fadq.qc.ca/documents/donnees/base-de-donnees-des-parcelles-et-productions-agricoles-declarees/
| Type | Vecteur (polygones) |
| Format | Shapefile / GeoPackage ect... |
| Utilité | Délimitation officielle des parcelles agricoles servant d’entrée aux dates T1 et T2 |
| Remarque | La BDPPAD fournit une segmentation précise des limites de parcelles agricoles utilisée comme base de comparaison pour l’analyse d’évolution |





### Contraintes sur les données
- Les deux couches doivent être **polygonales**.  
- Elles doivent représenter les **mêmes unités spatiales** (mêmes secteurs agricoles).  
- Les géométries doivent être valides (corrigées au besoin via `Fix Geometries`).  
- Les champs attributaires doivent contenir un **identifiant unique** par parcelle, ou le plugin en crée un si absent.

---

## 3. Approche et méthodologie détaillées

L’analyse se déroule en 7 grandes étapes :

### **Étape 1 – Récupération et validation des couches**
- Vérification que les deux couches sélectionnées sont bien des **polygones**.
- Vérification du **CRS** :  
  - si T1 et T2 ont des systèmes différents, reprojection automatique de T2 vers T1.
- Correction des géométries invalides.

### **Étape 2 – Préparation des champs**
Ajout automatique (si manquant) de :
- `ID_T1` ou `ID_T2`  
- `A_T1` (surface à T1)  
- `A_T2` (surface calculée au niveau de T1)

Toutes les surfaces sont calculées en **mètres carrés** puis converties en **hectares**.

### **Étape 3 – Intersection spatiale**
L’opération clé est : Intersection = T1 ∩ T2

Elle permet de déterminer :
- quelles zones de T1 existent encore à T2 ;
- quelle surface T2 recouvre chaque parcelle T1.

### **Étape 4 – Agrégation des surfaces T2**
Pour chaque parcelle de T1 :
- on additionne les surfaces intersectées provenant de T2  
⇒ cela donne la surface équivalente `A_T2_eq`.

### **Étape 5 – Calcul des variations**
Pour chaque parcelle T1 :
ΔA = A_T2_eq − A_T1
Δ% = (ΔA / A_T1) × 100

Les calculs tiennent compte :
- des valeurs nulles (A_T2_eq = 0 → parcelle disparue)
- des micro-différences (géométrie, arrondis)

### **Étape 6 – Classification des parcelles**
Le statut final est déterminé selon :

#### **1) Parcelles disparues**
Si `A_T2_eq = 0`  
→ `STATUT = "DISPARUE"`

#### **2) Parcelles conservées**
Si `A_T2_eq > 0` :

- `|Δ%| ≤ seuil` → `CONSERVÉE_STABLE`
- `Δ% > seuil` → `CONSERVÉE_AUGMENTÉE`
- `Δ% < -seuil` → `CONSERVÉE_DIMINUÉE`

#### **3) Nouvelles parcelles (option “Détecter nouvelles à T2”)**
Si une parcelle T2 ne correspond à aucune T1 → `NOUVELLE_PARCELLE`.

### **Étape 7 – Génération de la couche de sortie**
Création d’une nouvelle couche vectorielle contenant :

| Champ | Description |
|--------|-------------|
| `ID_T1` | Identifiant parcelle T1 |
| `A_T1_HA` | Surface à T1 |
| `A_T2_HA` | Surface équivalente à T2 |
| `DELTA_HA` | Variation absolue |
| `DELTA_%` | Variation relative |
| `STATUT` | Catégorie de changement |

L’utilisateur peut :
- l’enregistrer en mémoire  
- ou exporter vers SHP, GPKG, etc.

---

## 4. Outils et technologies

- **Langage** : Python (via l’API PyQGIS)
- **Plateforme** : QGIS 3.22+
- **Bibliothèques internes** :  
  - `QgsVectorLayer`  
  - `QgsGeometry`  
  - `QgsOverlayAnalyzer`  
  - `QgsProcessing` (intersection, union, agrégation)

---

## 5. Répartition des tâches dans l’équipe

| Membre | Rôle |
|--------|------|
| **Abdoulaye Gueye** | Interface Qt, gestion des couches, logique de surface |
| **Dabakh Mbow** | Calculs géométriques, interpolation T1 → T2 |
| **Dieumbe Fall** | Génération de la couche finale, test et validation |

---

## 6. Perspectives d’amélioration (v2)

- Support des couches non polygonales (points/lignes) via buffer automatique.  
- Analyse multi-temporelle (T1 → T2 → T3 → …).  
- Création d’un tableau de bord interactif (Graphiques + statistiques).  
- Connexion à des bases de données (PostGIS) pour analyses massives.  

---





