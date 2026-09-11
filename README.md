# Veille ADS — Perso (Ollama / Gemini + LangChain v19)

**Fichiers à importer (seule source à jour) :**
- `veille-ads-perso-ollama-v19.json` — **27 nœuds** (gate Ollama + 2 chains LangChain)
- `veille-ads-perso-gemini-v19.json` — **24 nœuds**

**Script de build :** `build_veille_v19.py` (remplace `build_veille_v18.py`, conservé pour historique local)

**Variante client (livraison, max 3 articles) :** voir [`../veille-client/README.md`](../veille-client/README.md) et `veille-ads-client-v18.json`.

## Vue d'ensemble

Veille **usage personnel** : pipeline **6 RSS publishers** + **Jina**, sans plafond d’articles, exclusion des articles **⬇️ Faible**, **deux Basic LLM Chains** (résumé + idée post LinkedIn), **upsert Notion** (compléter Résumé / LinkedIn manquants), timezone **Europe/Paris**.

| Critère | Client v18 | Perso v19 |
|--------|------------|-----------|
| LLM | Gemini cloud | **Ollama** `qwen2.5:14b` **ou** Gemini |
| Chaînes LangChain | 1 (résumé) | 2 (résumé + LinkedIn) |
| Max articles/run | 3 | **Aucune limite** |
| Faible pertinence | Gardée | **Filtrée** |
| Notion | Create natif | **PATCH** update + **POST** create |
| Cron | Lun–Ven 7h/13h | **Tous les jours** 7h/13h |
| LinkedIn | Non | Colonne **Idée post LinkedIn** |
| Gate Ollama | Non | **Check Ollama UP** → IF **qwen** → sinon Stop |
| Filtre / IF n8n | filter/if v2 | **filter/if v2.2** (conditions v2) |
| chainLlm | continueOnFail | **+ onError: continueErrorOutput** |

## Correspondance archive

Historique complet : [`../_archive/README-veille-lineage.md`](../_archive/README-veille-lineage.md).

| Ancien fichier | Statut | Remplacement |
|----------------|--------|--------------|
| `_archive/veille-ads-gnews-notion-telegram.json` | Figé (base client) | Client v18 + perso v19 |
| `_archive/veille-ads-ollama-local-v2.json` | Archivé | `veille-ads-perso-ollama-v19.json` |
| `_archive/veille-ads-gemini-flash-v1.json` | Archivé | `veille-ads-perso-gemini-v19.json` |
| `veille-ads-perso-*-v3.json` | Supprimé (regénérer v19) | Fichiers v19 ci-dessus |

## Import dans n8n

1. Choisir **un seul** workflow actif : Ollama (local) **ou** Gemini (cloud).
2. **Import from file** → JSON v19 correspondant.
3. Credentials :
   - **Notion account** — getAll + HTTP API (PATCH/POST pages).
   - **Ollama Local** (Ollama) — base URL `http://host.orb.internal:11434`.
   - **Google Gemini API** (Gemini) — sous-modèle LangChain.
   - **Telegram account** — `chatId` `6587303725`.
4. (Ollama) Vérifier que `qwen2.5:14b` est pull ; une exécution manuelle doit passer **Check Ollama UP** → **Ollama disponible ?**.
5. Tags workflow n8n : `veille`, `perso`, `langchain`, `v19`, `ollama`|`gemini`.
6. Activer le workflow.

## Migration depuis les workflows HTTP v2

Si vous utilisiez `veille-ads-ollama-local-v2.json` ou `veille-ads-gemini-flash-v1.json` :

1. **Désactiver** l’ancien workflow (HTTP `/api/generate` ou appels Gemini bruts).
2. **Importer** le v19 correspondant — les prompts et assemblers lisent `text` / `output` des **chainLlm**, pas des réponses HTTP custom.
3. **Re-créer les credentials** sur les nœuds LangChain (`lmChatOllama` / `lmChatGoogleGemini`).
4. Notion : le v19 utilise **upsert** (pages incomplètes reprises via `needsUpdate`) — pas de changement de schéma DB (`371e27a7-f3e3-8104-abf3-ec5d673086f3`).
5. Telegram : inchangé (branche parallèle depuis **Assembler Article + Résumé IA**, filtre 🔥 Haute).

## Credentials

| Credential | Ollama v19 | Gemini v19 |
|------------|------------|------------|
| Notion account | Oui | Oui |
| Ollama Local | Oui | — |
| Google Gemini API | — | Oui |
| Telegram account | Oui | Oui |

## Cron & timezone

- **Expression :** `0 7,13 * * *` — 7h et 13h **chaque jour** (Europe/Paris via `settings.timezone`).
- Plus agressif que le client (Lun–Ven) pour capter les actus US le week-end.

## Pattern LangChain (v19)

- Deux nœuds **`chainLlm` v1.9** avec **`onError: continueErrorOutput`** (résumé + LinkedIn).
- Un **Chat Model** relié aux deux chains via **`ai_languageModel`**.
- Prompt résumé : **3 points avec bullet •** (aligné archive gnews + client v18).

### Flux Ollama (gate)

```
Schedule → Check Ollama UP (GET /api/tags)
         → Ollama disponible ? (JSON contient "qwen")
              ├─ oui → Charger URLs Notion → … pipeline …
              └─ non → Stop — Ollama indisponible
```

### Flux Gemini

```
Schedule → Charger URLs Notion → … (pas de nœuds Ollama)
```

### Flux article (commun)

```
… → RSS×6 → Merge → Filtrer + Formater → Jina
  → Résumé Chain → Assembler Résumé ─┬→ LinkedIn Chain → Assembler LI → Build Payload → IF upsert → PATCH/POST
                                    └→ Filtre Haute (v2.2) → Telegram
```

---

## Documentation nœud par nœud

### Guide — Veille Perso v19
| | |
|--|--|
| **TYPE** | stickyNote |
| **RÔLE** | Aide-mémoire canvas (Ollama vs Gemini, v19) |

### 7h + 13h — Tous les jours
| | |
|--|--|
| **TYPE** | scheduleTrigger `0 7,13 * * *` |
| **RÔLE** | Déclenche la collecte 2×/jour, 7j/7 |
| **SORTIE Ollama** | → **Check Ollama UP** |
| **SORTIE Gemini** | → **Charger URLs Notion** |

### Check Ollama UP *(Ollama uniquement)*
| | |
|--|--|
| **TYPE** | httpRequest GET `{base}/api/tags` |
| **RÔLE** | Health check avant toute charge Notion/RSS |
| **POURQUOI** | Éviter des centaines d’appels Jina/LLM si OrbStack/Ollama est down |

### Ollama disponible ? *(Ollama uniquement)*
| | |
|--|--|
| **TYPE** | if **v2.2** (conditions **version 2**) |
| **CONDITION** | `JSON.stringify($json)` **contient** `qwen` |
| **TRUE** | → Charger URLs Notion |
| **FALSE** | → Stop — Ollama indisponible |

### Stop — Ollama indisponible *(Ollama uniquement)*
| | |
|--|--|
| **TYPE** | stopAndError |
| **RÔLE** | Arrêt explicite avec message (pull `qwen2.5:14b`, OrbStack) |

### Charger URLs Notion
| | |
|--|--|
| **TYPE** | notion getAll (DB `371e27a7-…`) |
| **RÔLE** | Liste pages + Résumé / Idée post LinkedIn / URL |
| **POURQUOI** | Base upsert (`needsUpdate`) |

### Initialiser mémoire
| | |
|--|--|
| **TYPE** | code |
| **RÔLE** | `processedUrls` + `needsUpdate[url]` si champs IA manquants |
| **SORTIE** | Fan-out vers 6 RSS |

### RSS ×6 + Fusionner 6 flux
| | |
|--|--|
| **TYPE** | rssFeedRead + merge append |
| **SOURCES** | SEL, AdExchanger, PPC Hero, SEJ, n8n Blog, WordStream |

### Filtrer + Formater
| | |
|--|--|
| **TYPE** | code |
| **RÔLE** | Mots-clés (+ `marketing digital`, `programmatic`, `agenc`), tag **Agences**, score **api**, skip **Faible**, **pas** de `.slice(0,3)`, flags `_updateMode` / `_pageId` / `_needsResume` / `_needsLinkedin` |

### Jina — Lire Article
| | |
|--|--|
| **TYPE** | code (fetch r.jina.ai) |
| **RÔLE** | Contenu long pour LLM |

### Résumé IA — Basic LLM Chain
| | |
|--|--|
| **TYPE** | chainLlm **1.9**, `onError: continueErrorOutput` |
| **RÔLE** | Synthèse FR **3× •** |

### Post LinkedIn — Basic LLM Chain
| | |
|--|--|
| **TYPE** | chainLlm **1.9**, `onError: continueErrorOutput` |
| **INPUT** | Titre + `ai_summary` depuis branche Assembler |

### Ollama Chat Model / Google Gemini Chat Model
| | |
|--|--|
| **TYPE** | lmChatOllama `qwen2.5:14b` **ou** lmChatGoogleGemini `gemini-2.5-flash` |
| **LIEN** | 2 cibles `ai_languageModel` (résumé + LinkedIn) |

### Assembler Article + Résumé IA
| | |
|--|--|
| **TYPE** | code |
| **RÔLE** | `ai_summary`, `telegramMsg` ; **double** branche main (LinkedIn + Telegram) |

### Assembler Post LinkedIn
| | |
|--|--|
| **TYPE** | code |
| **RÔLE** | Champ `linkedinPost` |

### Build Notion Payload
| | |
|--|--|
| **TYPE** | code |
| **RÔLE** | Properties Notion partielles (update) ou complètes (create) |

### Nouveau ou Mise à jour ?
| | |
|--|--|
| **TYPE** | if **v2.2**, `$json._updateMode === true` |
| **TRUE** | PATCH · **FALSE** | POST |

### Notion — Mettre à jour Page / Créer Page
| | |
|--|--|
| **TYPE** | httpRequest PATCH/POST |
| **OPTIONS** | `continueOnFail: true` |

### Seulement Haute pertinence
| | |
|--|--|
| **TYPE** | filter **v2.2** (conditions v2), pertinence contient `Haute` |

### Telegram — Alerte
| | |
|--|--|
| **TYPE** | telegram, `continueOnFail: true` |
| **RÔLE** | Alertes 🔥 uniquement |

---

## Regénérer les JSON

```bash
cd veille-perso
python3 build_veille_v19.py
```

| Fichier | Nœuds |
|---------|-------|
| veille-ads-perso-ollama-v19.json | 27 |
| veille-ads-perso-gemini-v19.json | 24 |

Validation : le script re-parse chaque JSON après écriture.
