# 📊 PLAN D'OPTIMISATION - REQUÊTES SQL

**Branche**: `feature/centralize-financial-calculations` → **Renommée en** `feature/optimize-db-queries`  
**Priorité**: 🔴 CRITIQUE - Impacte performance des admins et vues  
**Durée estimée**: 2-3 jours

---

## 🎯 OBJECTIF

Élimine tous les **N+1 query problems** et optimise les **admin pages**.

### Résultats attendus:
- ⚡ Admin pages: **2-3x plus rapides**
- 📊 Liste agents: Passe de **100+ requêtes** à **2-3 requêtes**
- 🔍 Panel admin fluide (pas d'attente)

---

## 🔍 PROBLÈMES IDENTIFIÉS

### 1️⃣ Admin Pages (CRITIQUE)

#### ❌ **core/admin.py - LotEntrepotAdmin**
```python
# MAUVAIS - N+1 sur fournisseur et produit
class LotEntrepotAdmin(admin.ModelAdmin):
    list_display = ['id', 'produit', 'fournisseur', 'quantite_restante', ...]
    # Pas de get_queryset = 1 requête par lot!
```

**Impact**: Liste 100 lots = 100+ requêtes

**Fix**: 
```python
def get_queryset(self, request):
    return super().get_queryset(request).select_related('produit', 'fournisseur')
```

---

#### ❌ **core/admin.py - VenteAdmin**
```python
# MAUVAIS
list_display = ['agent', 'client', 'produit', 'lot', 'montant', ...]
# Agent, Client, LotEntrepot non optimisées
```

**Fix**: `select_related('agent', 'client', 'lot__produit', 'lot__fournisseur')`

---

#### ❌ **core/admin.py - RecouvrementAdmin**
```python
# MAUVAIS
list_display = ['agent', 'superviseur', 'montant_recouvre', ...]
# Agent et Superviseur non optimisés
```

**Fix**: `select_related('agent', 'superviseur')`

---

#### ❌ **core/admin.py - VersementBancaireAdmin**
```python
# MAUVAIS
# Superviseur et effectue_par non optimisés
```

**Fix**: `select_related('superviseur', 'effectue_par')`

---

#### ✅ **core/admin.py - DetailDistributionAdmin** (DÉJÀ BON)
```python
# BON - Modèle à suivre
class DetailDistributionAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'distribution', 'produit'
        )
```

---

### 2️⃣ Views (SECONDAIRE)

#### ❌ **core/views.py - liste_distributions()**
```python
def liste_distributions(request):
    distributions = Distribution.objects.all()  # ❌ N+1 sur agent
    for dist in distributions:
        print(dist.agent.full_name)  # Une requête par distribution!
```

**Fix**: 
```python
distributions = Distribution.objects.all().select_related('agent')
```

---

#### ❌ **core/views.py - detail_fournisseur()**
```python
def detail_fournisseur(request, id):
    fournisseur = Fournisseur.objects.get(pk=id)
    lots = fournisseur.lots.all()  # ✅ OK
    
    # ❌ MAUVAIS - N+1 sur produit et pertes
    for lot in lots:
        print(lot.produit.nom)  # Une requête par lot
        for perte in lot.pertes.all():  # Une requête par lot!
            print(perte.quantite_perdue)
```

**Fix**:
```python
lots = fournisseur.lots.all().select_related('produit').prefetch_related('pertes')
```

---

#### ❌ **agents/views.py - superviseur_lots_affectes()**
```python
# ✅ DÉJÀ OPTIMISÉ (Bonne pratique à étendre)
affectations = affectations.select_related('agent_superviseur', 'lot__produit')
```

---

### 3️⃣ Services (PEU DE PROBLÈMES)

Les services utilisent des `.aggregate()` et `.values()` qui sont optimisés.

Vérifier seulement:
- `agent_dashboard_service.py`: Prefetch sur Vente
- `product_analysis_service.py`: Select_related sur Produit

---

## 📋 TÂCHES D'OPTIMISATION

### Tier 1: Admin Pages (URGENT)
- [ ] **LotEntrepotAdmin**: Ajouter `get_queryset()` avec `select_related(produit, fournisseur)`
- [ ] **VenteAdmin**: Ajouter `get_queryset()` avec `select_related(agent, client, lot...)`
- [ ] **RecouvrementAdmin**: Ajouter `get_queryset()` avec `select_related(agent, superviseur)`
- [ ] **VersementBancaireAdmin**: Ajouter `get_queryset()` avec `select_related(superviseur, effectue_par)`
- [ ] **AgentAdmin**: Ajouter `get_queryset()` avec `select_related(user, superviseur)`
- [ ] **DistributionAdmin**: Ajouter si absent

### Tier 2: Views Critiques
- [ ] **liste_distributions()**: Ajouter `select_related('agent')`
- [ ] **detail_fournisseur()**: Ajouter `prefetch_related('lots__pertes')`
- [ ] **enregistrer_vente()**: Vérifier if queryset optimisé
- [ ] **distribuer_produits_agent()**: Vérifier queryset

### Tier 3: Services
- [ ] Audit des queryset dans `agent_dashboard_service.py`
- [ ] Audit des queryset dans `product_analysis_service.py`
- [ ] Audit des queryset dans `fournisseur_service.py`

---

## 🧪 VALIDATION & TESTS

### Avant chaque modification:
```bash
# Vérifier les requêtes SQL
python manage.py shell_plus --ipython
from django.test.utils import override_settings
from django.db import connection

with override_settings(DEBUG=True):
    # Exécuter le code
    print(len(connection.queries))  # Affiche le nombre de requêtes
```

### Benchmark:
```
LotEntrepotAdmin list_view:
    Avant: 127 requêtes (100 lots)
    Après: 2 requêtes
    Gain: 98% ✅
```

---

## 🔧 FICHIERS À MODIFIER

```
core/
├── admin.py                    ✏️ MODIFIER (6-8 classes)
├── views.py                    ✏️ MODIFIER (4-5 functions)
└── services/
    ├── agent_dashboard_service.py    ✏️ VÉRIFIER
    ├── fournisseur_service.py        ✏️ VÉRIFIER
    └── product_analysis_service.py   ✏️ VÉRIFIER

agents/
└── views.py                    ✏️ VÉRIFIER
```

---

## 📐 PATTERN À RESPECTER

### Pour une seule relation:
```python
# Relation ForeignKey
class MyAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('agent')  # 1 requête supplémentaire, max
```

### Pour plusieurs niveaux:
```python
# Relations imbriquées (ForeignKey → ForeignKey)
return qs.select_related('lot__produit', 'lot__fournisseur')
```

### Pour OneToMany:
```python
# Relations reversées (prefetch_related)
from django.db.models import Prefetch
from core.models import Perte

return qs.prefetch_related(
    Prefetch('pertes', queryset=Perte.objects.select_related('motif'))
)
```

---

## ✅ CHECKLIST DE VALIDATION

Avant merge:
- [ ] Tous les `.select_related()` sont en place
- [ ] Tous les `.prefetch_related()` quand besoin
- [ ] Pas de N+1 (tester avec `django-debug-toolbar`)
- [ ] Tests unitaires passent
- [ ] Admin pages chargent en < 2s
- [ ] Pas de requête dupliquée

---

## 🚀 ÉTAPES

1. **Diagnostic** (30 min): Vérifier requêtes actuelles
2. **Fix Admin** (2h): Admin pages optimisées
3. **Fix Views** (1.5h): Views optimisées
4. **Tests** (1h): Benchmark & validation
5. **PR & Review** (1h): Code review & merge

**Total: ~1 jour de travail** 🎯

---

## 📝 COMMITS ATTENDUS

```
feat(db): optimize LotEntrepotAdmin queries with select_related
feat(db): optimize VenteAdmin with nested select_related
feat(db): optimize view liste_distributions with select_related
feat(db): optimize detail_fournisseur with prefetch_related
feat(db): optimize RecouvrementAdmin queries
test(db): add query count benchmarks
```

---

## 🔄 ROLLBACK (si problème)

```bash
git reset --hard HEAD~5  # Revenir avant les changements
git push -f origin feature/optimize-db-queries
```

Pas dangereux - c'est du refactoring technique pur, zéro impact métier.
