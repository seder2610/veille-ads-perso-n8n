#!/usr/bin/env python3
"""Génère veille-ads-perso-ollama-v19.json et veille-ads-perso-gemini-v19.json."""
import json
from pathlib import Path

VEILLE_DB_ID = "371e27a7-f3e3-8104-abf3-ec5d673086f3"
NOTION_CRED = {"id": "4rbkLchn0g0a74Te", "name": "Notion account"}
TELEGRAM_CRED = {"id": "cAqYgyvMNZd6mPlk", "name": "Telegram account"}
GEMINI_CRED = {"id": "mTD96rhOwH0wn5rL", "name": "Google Gemini API"}
OLLAMA_CRED = {"id": "PLACEHOLDER_OLLAMA", "name": "Ollama Local"}
OLLAMA_BASE = "http://host.orb.internal:11434"

RSS_FEEDS = [
    ("https://searchengineland.com/feed", "Search Engine Land"),
    ("https://www.adexchanger.com/feed", "AdExchanger"),
    ("https://www.ppchero.com/feed", "PPC Hero"),
    ("https://www.searchenginejournal.com/feed", "Search Engine Journal"),
    ("https://blog.n8n.io/rss", "n8n Blog"),
    ("https://www.wordstream.com/blog/feed", "WordStream"),
]

DIR = Path(__file__).resolve().parent

SEED_CODE = r"""
const pages = $input.all();

const urlMap = {};
const fullUrls = [];

for (const p of pages) {
  const props = p.json?.properties || {};
  const urlProp = props['URL'] || props['url'] || props['Url'];
  const url = urlProp?.url || '';
  if (!url || !url.startsWith('http')) continue;

  const pageId = p.json?.id || '';
  const resumeArr = props['Résumé']?.rich_text || props['Resume']?.rich_text || [];
  const linkedinArr = props['Idée post LinkedIn']?.rich_text
    || props['Idee post LinkedIn']?.rich_text
    || props['idée post linkedin']?.rich_text || [];

  const hasResume   = resumeArr.length > 0 && (resumeArr[0]?.text?.content || '').trim().length > 10;
  const hasLinkedin = linkedinArr.length > 0 && (linkedinArr[0]?.text?.content || '').trim().length > 10;

  if (hasResume && hasLinkedin) {
    fullUrls.push(url);
  } else {
    urlMap[url] = { pageId, hasResume, hasLinkedin };
  }
}

const wfData = $workflow.staticData;
if (wfData) {
  const current = new Set(Array.isArray(wfData.processedUrls) ? wfData.processedUrls : []);
  fullUrls.forEach(u => current.add(u));
  wfData.processedUrls = [...current].slice(-2000);
  wfData.needsUpdate = urlMap;
}

return [{ json: { ready: true, total: pages.length, aCompleter: Object.keys(urlMap).length } }];
""".strip()

FILTER_PERSO = r"""
const items = $input.all();
const results = [];
const wfData = $workflow.staticData;
const processedSet = new Set((wfData && wfData.processedUrls) ? wfData.processedUrls : []);
const needsUpdate = (wfData && wfData.needsUpdate) ? wfData.needsUpdate : {};
const newUrls = [];

function decode(str) {
  return str.replace(/&nbsp;/g,' ').replace(/&amp;/g,'&').replace(/&lt;/g,'<')
            .replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#(\d+);/g,(_,n)=>String.fromCharCode(n))
            .replace(/\s+/g,' ').trim();
}

for (const item of items) {
  const d = item.json;
  const title = decode((d.titre || d.title || '').replace(/<[^>]+>/g, ''));
  const url   = d.lien || d.link || d.url || '';
  const pubDate = d['date de publication'] || d.pubDate || d.isoDate || '';
  const snippet = decode((d.content||d.contenu||d['extrait de contenu']||d.summary||d.contentSnippet||'')
    .replace(/<[^>]+>/g,'').slice(0,800));
  const source = (d.source?.name || d.feed?.title || 'Autre').replace(/ - RSS.*$/i,'').trim();

  if (!title || !url || !url.startsWith('http')) continue;
  if (newUrls.includes(url)) continue;
  if (processedSet.has(url)) continue;

  const pub = new Date(pubDate);
  if (pubDate && !isNaN(pub.getTime()) && (Date.now() - pub.getTime()) > 604800000) continue;

  const text = (title + ' ' + snippet).toLowerCase();
  const relevant = ['google ads','adwords','ppc','paid search','paid media','meta ads','facebook ads',
    'automation','automatisation','n8n','workflow','ai ','artificial intelligence','machine learning',
    'ad spend','campaign','cpc','roas','impression','bidding','performance max','smart bidding',
    'agenc','marketing digital','programmatic'];
  if (!relevant.some(w => text.includes(w))) continue;

  const tags = [];
  if (text.includes('google ads')||text.includes('adwords')||text.includes('paid search')) tags.push('Google Ads');
  if (text.includes('meta')||text.includes('facebook ads')) tags.push('Meta Ads');
  if (text.includes('automation')||text.includes('automatisation')) tags.push('Automation');
  if (text.includes('n8n')) tags.push('n8n');
  if (text.includes(' ai ')||text.includes('artificial intelligence')||text.includes('machine learning')) tags.push('IA');
  if (text.includes('agenc')||text.includes('agence')) tags.push('Agences');
  if (tags.length === 0) tags.push('Technologie');

  const highValue = ['automation','n8n','workflow','google ads','ppc','performance max','smart bidding','roas','api'];
  const score = highValue.filter(w => text.includes(w)).length;
  const pertinence = score >= 3 ? '🔥 Haute' : score >= 1 ? '🟡 Moyenne' : '⬇️ Faible';
  if (pertinence === '⬇️ Faible') continue;

  const pubISO = !isNaN(pub.getTime()) ? pub.toISOString() : new Date().toISOString();
  newUrls.push(url);

  const existing = needsUpdate[url];
  if (existing) {
    results.push({ json: { title, url, source, snippet, tags, pertinence, pubISO,
      _updateMode: true, _pageId: existing.pageId,
      _needsResume: !existing.hasResume, _needsLinkedin: !existing.hasLinkedin }});
  } else {
    results.push({ json: { title, url, source, snippet, tags, pertinence, pubISO, _updateMode: false }});
  }
}

if (wfData) wfData.processedUrls = [...processedSet, ...newUrls].slice(-2000);
const order = {'🔥 Haute': 0, '🟡 Moyenne': 1};
return results.sort((a,b) => (order[a.json.pertinence]??1) - (order[b.json.pertinence]??1));
""".strip()

JINA_CODE = r"""
const item = $input.item.json;
let articleContent = item.snippet || '';

try {
  const jinaResp = await fetch(`https://r.jina.ai/${item.url}`, {
    headers: { 'Accept': 'text/plain', 'X-Return-Format': 'text', 'X-Timeout': '10' }
  });
  const text = await jinaResp.text();
  if (text && text.length > 300
      && !text.includes('SecurityCompromiseError')
      && !text.toLowerCase().startsWith('error')) {
    articleContent = text.slice(0, 4000);
  }
} catch(e) {}

return { json: { ...item, articleContent } };
""".strip()

SUMMARY_PROMPT = (
    "Tu es un expert en marketing digital, publicite payante (Google Ads, Meta Ads) et automation marketing.\n"
    "Ta mission : analyser cet article et produire une SYNTHESE ACTIONNABLE pour une agence PPC/automation.\n\n"
    "REGLES :\n"
    "- Langue : francais uniquement\n"
    "- Format : exactement 3 points cles introduits par le symbole bullet point (•)\n"
    "- Longueur : 120 mots maximum au total\n"
    "- Angle : ce que cela signifie concretement pour une agence (opportunite, risque, action)\n"
    "- Sois factuel et direct, zero generalite\n\n"
    "ARTICLE :\n"
    "Titre : {{ $json.title }}\n"
    "Source : {{ $json.source }}\n"
    "Contenu : {{ $json.articleContent }}"
)

LINKEDIN_PROMPT = (
    "Tu es un expert LinkedIn pour les agences marketing digital.\n"
    "Écris un post LinkedIn percutant basé sur cet article (consultant automation / Google Ads / n8n).\n\n"
    "RÈGLES :\n"
    "- Français, 150-200 mots max\n"
    "- Accroche forte → 2-3 insights → question ou CTA\n"
    "- Ton direct, expert, pas corporate\n"
    "- Max 3 hashtags spécifiques en fin de post\n"
    "- Commence par l'accroche, pas par \"Je viens de lire...\"\n\n"
    "Article : {{ $json.title }}\n"
    "Résumé : {{ $json.ai_summary }}\n\n"
    "Post LinkedIn :"
)

ASSEMBLER_RESUME = r"""
const aiOutput = ($input.item.json.text || $input.item.json.output || '').trim();
const orig = $('Jina — Lire Article').item.json;
const emoji = orig.pertinence?.includes('Haute') ? '🔥' : '📡';
const telegramMsg = `${emoji} *${orig.title}*\n\n${aiOutput}\n\n🔗 ${orig.url}`;
const { articleContent, ...origClean } = orig;
return { json: { ...origClean, ai_summary: aiOutput, telegramMsg } };
""".strip()

ASSEMBLER_LINKEDIN = r"""
const linkedinPost = ($input.item.json.text || $input.item.json.output || '').trim();
const prev = $('Assembler Article + Résumé IA').item.json;
return { json: { ...prev, linkedinPost } };
""".strip()

NOTION_PAYLOAD = f"""
const d = $input.item.json;
const props = {{}};

if (!d._updateMode || d._needsResume) {{
  props['Résumé'] = {{ rich_text: [{{ text: {{ content: (d.ai_summary || d.snippet || '').slice(0,2000) }} }}] }};
}}
if (!d._updateMode || d._needsLinkedin) {{
  props['Idée post LinkedIn'] = {{ rich_text: [{{ text: {{ content: (d.linkedinPost || '').slice(0,2000) }} }}] }};
}}
if (!d._updateMode) {{
  props['Titre']       = {{ title: [{{ text: {{ content: d.title || '' }} }}] }};
  props['Source']      = {{ select: {{ name: d.source || 'Autre' }} }};
  props['URL']         = {{ url: d.url || null }};
  props['Tags']        = {{ multi_select: (d.tags || []).map(t => ({{ name: t }})) }};
  props['Date']        = {{ date: {{ start: d.pubISO }} }};
  props['Pertinence']  = {{ select: {{ name: d.pertinence || '🟡 Moyenne' }} }};
}}

return {{ json: {{
  _updateMode: !!d._updateMode,
  _pageId: d._pageId || '',
  parent: {{ database_id: '{VEILLE_DB_ID}' }},
  properties: props,
  _telegramMsg: d.telegramMsg || '',
  _pertinence: d.pertinence
}} }};
""".strip()


def build_workflow(backend: str):
    is_ollama = backend == "ollama"
    wf_name = (
        "Veille ADS — Perso (Ollama + LangChain) v19"
        if is_ollama
        else "Veille ADS — Perso (Gemini + LangChain) v19"
    )
    model_node_name = "Ollama Chat Model" if is_ollama else "Google Gemini Chat Model"

    nodes = []
    x = 200

    sticky = (
        "## Veille ADS Perso v3\n"
        + ("Ollama qwen2.5:14b local — " if is_ollama else "Gemini 2.5-flash — ")
        + "2 Basic LLM Chains (résumé + LinkedIn)\n"
        "Upsert Notion (HTTP PATCH/POST) · Telegram 🔥 Haute\n"
        "Cron : 7h et 13h tous les jours"
    )
    nodes.append({
        "id": "guide",
        "name": "Guide — Veille Perso v19",
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [x - 80, 40],
        "parameters": {"width": 540, "height": 200, "content": sticky},
    })

    nodes.append({
        "id": "trigger",
        "name": "7h + 13h — Tous les jours",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": [x, 300],
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": "0 7,13 * * *"}]}
        },
    })

    nodes.append({
        "id": "load-notion-urls",
        "name": "Charger URLs Notion",
        "type": "n8n-nodes-base.notion",
        "typeVersion": 2.2,
        "position": [x + 280, 300],
        "alwaysOutputData": True,
        "parameters": {
            "resource": "databasePage",
            "operation": "getAll",
            "databaseId": {"__rl": True, "value": VEILLE_DB_ID, "mode": "id"},
            "returnAll": True,
            "options": {},
        },
        "credentials": {"notionApi": NOTION_CRED},
    })

    nodes.append({
        "id": "seed-memory",
        "name": "Initialiser mémoire",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 560, 300],
        "parameters": {"jsCode": SEED_CODE},
    })

    rss_names = []
    for i, (feed_url, feed_name) in enumerate(RSS_FEEDS):
        name = f"RSS — {feed_name}"
        rss_names.append(name)
        nodes.append({
            "id": f"rss-{i}",
            "name": name,
            "type": "n8n-nodes-base.rssFeedRead",
            "typeVersion": 1,
            "position": [x + 840, 60 + i * 120],
            "parameters": {"url": feed_url},
        })

    nodes.append({
        "id": "merge",
        "name": "Fusionner 6 flux",
        "type": "n8n-nodes-base.merge",
        "typeVersion": 3,
        "position": [x + 1120, 400],
        "parameters": {"mode": "append"},
    })

    nodes.append({
        "id": "format",
        "name": "Filtrer + Formater",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 1360, 400],
        "parameters": {"jsCode": FILTER_PERSO},
    })

    nodes.append({
        "id": "fetch-content",
        "name": "Jina — Lire Article",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 1600, 400],
        "parameters": {"jsCode": JINA_CODE, "mode": "runOnceForEachItem"},
    })

    nodes.append({
        "id": "llm-resume",
        "name": "Résumé IA — Basic LLM Chain",
        "type": "@n8n/n8n-nodes-langchain.chainLlm",
        "typeVersion": 1.9,
        "position": [x + 1840, 400],
        "continueOnFail": True,
        "onError": "continueErrorOutput",
        "parameters": {"promptType": "define", "text": SUMMARY_PROMPT},
    })

    nodes.append({
        "id": "llm-linkedin",
        "name": "Post LinkedIn — Basic LLM Chain",
        "type": "@n8n/n8n-nodes-langchain.chainLlm",
        "typeVersion": 1.9,
        "position": [x + 2320, 320],
        "continueOnFail": True,
        "onError": "continueErrorOutput",
        "parameters": {"promptType": "define", "text": LINKEDIN_PROMPT},
    })

    if is_ollama:
        nodes.append({
            "id": "check-ollama",
            "name": "Check Ollama UP",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [x + 140, 300],
            "parameters": {
                "method": "GET",
                "url": f"{OLLAMA_BASE}/api/tags",
                "options": {"timeout": 8000},
            },
        })
        nodes.append({
            "id": "if-ollama",
            "name": "Ollama disponible ?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [x + 420, 300],
            "parameters": {
                "conditions": {
                    "options": {
                        "caseSensitive": False,
                        "leftValue": "",
                        "typeValidation": "loose",
                        "version": 2,
                    },
                    "conditions": [{
                        "id": "ollama-qwen",
                        "leftValue": "={{ JSON.stringify($json) }}",
                        "rightValue": "qwen",
                        "operator": {"type": "string", "operation": "contains"},
                    }],
                    "combinator": "and",
                },
                "options": {},
            },
        })
        nodes.append({
            "id": "stop-ollama",
            "name": "Stop — Ollama indisponible",
            "type": "n8n-nodes-base.stopAndError",
            "typeVersion": 1,
            "position": [x + 420, 480],
            "parameters": {
                "errorType": "errorMessage",
                "errorMessage": "Ollama injoignable ou modèle qwen absent — vérifier OrbStack / ollama pull qwen2.5:14b",
            },
        })
        nodes.append({
            "id": "chat-model",
            "name": model_node_name,
            "type": "@n8n/n8n-nodes-langchain.lmChatOllama",
            "typeVersion": 1,
            "position": [x + 2080, 620],
            "parameters": {
                "model": "qwen2.5:14b",
                "options": {"temperature": 0.4, "numPredict": 400},
            },
            "credentials": {"ollamaApi": OLLAMA_CRED},
        })
    else:
        nodes.append({
            "id": "chat-model",
            "name": model_node_name,
            "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
            "typeVersion": 1,
            "position": [x + 2080, 620],
            "parameters": {
                "modelName": "gemini-2.5-flash",
                "options": {"temperature": 0.4, "maxOutputTokens": 450},
            },
            "credentials": {"googlePalmApi": GEMINI_CRED},
        })

    nodes.append({
        "id": "merge-ai",
        "name": "Assembler Article + Résumé IA",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 2080, 400],
        "parameters": {"jsCode": ASSEMBLER_RESUME, "mode": "runOnceForEachItem"},
    })

    nodes.append({
        "id": "merge-linkedin",
        "name": "Assembler Post LinkedIn",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 2560, 320],
        "parameters": {"jsCode": ASSEMBLER_LINKEDIN, "mode": "runOnceForEachItem"},
    })

    nodes.append({
        "id": "notion-payload",
        "name": "Build Notion Payload",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [x + 2800, 320],
        "parameters": {"jsCode": NOTION_PAYLOAD, "mode": "runOnceForEachItem"},
    })

    nodes.append({
        "id": "if-upsert",
        "name": "Nouveau ou Mise à jour ?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [x + 3040, 320],
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": False,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [{
                    "id": "c1",
                    "leftValue": "={{ $json._updateMode }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "equals"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
    })

    nodes.append({
        "id": "notion-patch",
        "name": "Notion — Mettre à jour Page",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x + 3280, 220],
        "continueOnFail": True,
        "parameters": {
            "method": "PATCH",
            "url": "={{ 'https://api.notion.com/v1/pages/' + $json._pageId }}",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "notionApi",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Notion-Version", "value": "2022-06-28"}]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ properties: $json.properties }) }}",
            "options": {},
        },
        "credentials": {"notionApi": NOTION_CRED},
    })

    nodes.append({
        "id": "notion-post",
        "name": "Notion — Créer Page",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [x + 3280, 420],
        "continueOnFail": True,
        "parameters": {
            "method": "POST",
            "url": "https://api.notion.com/v1/pages",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "notionApi",
            "sendHeaders": True,
            "headerParameters": {"parameters": [{"name": "Notion-Version", "value": "2022-06-28"}]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ parent: $json.parent, properties: $json.properties }) }}",
            "options": {},
        },
        "credentials": {"notionApi": NOTION_CRED},
    })

    nodes.append({
        "id": "filter-hot",
        "name": "Seulement Haute pertinence",
        "type": "n8n-nodes-base.filter",
        "typeVersion": 2.2,
        "position": [x + 2320, 560],
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": False,
                    "leftValue": "",
                    "typeValidation": "loose",
                    "version": 2,
                },
                "conditions": [{
                    "id": "1",
                    "leftValue": "={{ $json.pertinence }}",
                    "rightValue": "Haute",
                    "operator": {"type": "string", "operation": "contains"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
    })

    nodes.append({
        "id": "telegram",
        "name": "Telegram — Alerte",
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [x + 2560, 560],
        "continueOnFail": True,
        "parameters": {
            "chatId": "6587303725",
            "text": "={{ $json.telegramMsg }}",
            "additionalFields": {"parse_mode": "Markdown", "disable_web_page_preview": True},
        },
        "credentials": {"telegramApi": TELEGRAM_CRED},
    })

    conns = {}
    if is_ollama:
        conns["7h + 13h — Tous les jours"] = {"main": [[{"node": "Check Ollama UP", "type": "main", "index": 0}]]}
        conns["Check Ollama UP"] = {"main": [[{"node": "Ollama disponible ?", "type": "main", "index": 0}]]}
        conns["Ollama disponible ?"] = {
            "main": [
                [{"node": "Charger URLs Notion", "type": "main", "index": 0}],
                [{"node": "Stop — Ollama indisponible", "type": "main", "index": 0}],
            ]
        }
    else:
        conns["7h + 13h — Tous les jours"] = {"main": [[{"node": "Charger URLs Notion", "type": "main", "index": 0}]]}

    conns.update({
        "Charger URLs Notion": {"main": [[{"node": "Initialiser mémoire", "type": "main", "index": 0}]]},
        "Initialiser mémoire": {"main": [[{"node": n, "type": "main", "index": 0} for n in rss_names]]},
        "Fusionner 6 flux": {"main": [[{"node": "Filtrer + Formater", "type": "main", "index": 0}]]},
        "Filtrer + Formater": {"main": [[{"node": "Jina — Lire Article", "type": "main", "index": 0}]]},
        "Jina — Lire Article": {"main": [[{"node": "Résumé IA — Basic LLM Chain", "type": "main", "index": 0}]]},
        "Résumé IA — Basic LLM Chain": {"main": [[{"node": "Assembler Article + Résumé IA", "type": "main", "index": 0}]]},
        model_node_name: {
            "ai_languageModel": [[
                {"node": "Résumé IA — Basic LLM Chain", "type": "ai_languageModel", "index": 0},
                {"node": "Post LinkedIn — Basic LLM Chain", "type": "ai_languageModel", "index": 0},
            ]]
        },
        "Assembler Article + Résumé IA": {"main": [[
            {"node": "Post LinkedIn — Basic LLM Chain", "type": "main", "index": 0},
            {"node": "Seulement Haute pertinence", "type": "main", "index": 0},
        ]]},
        "Post LinkedIn — Basic LLM Chain": {"main": [[{"node": "Assembler Post LinkedIn", "type": "main", "index": 0}]]},
        "Assembler Post LinkedIn": {"main": [[{"node": "Build Notion Payload", "type": "main", "index": 0}]]},
        "Build Notion Payload": {"main": [[{"node": "Nouveau ou Mise à jour ?", "type": "main", "index": 0}]]},
        "Nouveau ou Mise à jour ?": {"main": [
            [{"node": "Notion — Mettre à jour Page", "type": "main", "index": 0}],
            [{"node": "Notion — Créer Page", "type": "main", "index": 0}],
        ]},
        "Seulement Haute pertinence": {"main": [[{"node": "Telegram — Alerte", "type": "main", "index": 0}]]},
    })

    for i, name in enumerate(rss_names):
        conns[name] = {"main": [[{"node": "Fusionner 6 flux", "type": "main", "index": i}]]}

    tag_backend = "ollama" if is_ollama else "gemini"
    return {
        "name": wf_name,
        "nodes": nodes,
        "connections": conns,
        "settings": {"executionOrder": "v1", "timezone": "Europe/Paris"},
        "tags": [
            {"name": "veille"},
            {"name": "perso"},
            {"name": "langchain"},
            {"name": "v19"},
            {"name": tag_backend},
        ],
        "staticData": None,
    }


def main():
    outputs = [
        ("ollama", DIR / "veille-ads-perso-ollama-v19.json"),
        ("gemini", DIR / "veille-ads-perso-gemini-v19.json"),
    ]
    for backend, out_path in outputs:
        wf = build_workflow(backend)
        out_path.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
        json.loads(out_path.read_text(encoding="utf-8"))
        print(f"Généré : {out_path} ({len(wf['nodes'])} nodes)")


if __name__ == "__main__":
    main()
