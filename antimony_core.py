import argparse
import ast
import base64
import calendar
import hashlib
import json
import math
import mimetypes
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import tkinter as tk
import random
import secrets
import string
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import filedialog, scrolledtext
from urllib import error, request
from urllib.parse import parse_qs, quote, quote_plus, urlencode, urlparse

try:
    import winreg
except ImportError:
    winreg = None

from config import load_config
from memory import MemoryView
from safety import PermissionGate, SafetyScanner


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "assistant_memory.db"
ASSET_DIR = APP_DIR / "assets"
API_HOST = "127.0.0.1"
API_PORT = 8765
VOICE_CACHE_DIR = APP_DIR / ".voice_cache"
SECRET_DIR = APP_DIR / ".secrets"
OPENAI_KEY_FILE = SECRET_DIR / "openai_key.txt"
KNOWLEDGE_DIR = APP_DIR / "knowledge"
CUSTOM_AGENTS_FILE = APP_DIR / "custom_agents.json"
URL_RE = re.compile(r"https?://[^\s)>\]}\"']+")
PUBLIC_DATA_USER_AGENT = "AntimonyAI/1.0 (local educational RAG assistant)"


PERSONAS = {
    "soren": {
        "name": "Soren",
        "label": "Local AI",
        "image": ASSET_DIR / "soren.png",
        "short": "calm and precise",
        "system": (
            "You are Soren, an original anime AI assistant. You are calm, powerful, "
            "witty, precise, protective, and scholarly. You explain complex things clearly."
        ),
        "hello": "Soren here. Bring me the impossible-looking problem; we will make it readable.",
        "voice": {"index": 0, "rate": 165, "volume": 0.92},
    },
    "renji": {
        "name": "Renji",
        "label": "Local AI",
        "image": ASSET_DIR / "renji.png",
        "short": "clever and direct",
        "system": (
            "You are Renji, an original anime AI assistant. You are clever, teasing, "
            "strategic, competitive, and secretly helpful. You push the user to think sharper."
        ),
        "hello": "Renji online. I will help, but I reserve the right to roast inefficient plans.",
        "voice": {"index": 1, "rate": 188, "volume": 0.96},
    },
    "kael": {
        "name": "Kael",
        "label": "Local AI",
        "image": ASSET_DIR / "kael.png",
        "short": "fast and practical",
        "system": (
            "You are Kael, an original anime AI assistant. You are fast, playful, tactical, "
            "confident, and direct. You prefer simple moves that work."
        ),
        "hello": "Kael here. Fast answer or full strategy? Either way, we move clean.",
        "voice": {"index": 2, "rate": 178, "volume": 0.94},
    },
    "mira": {
        "name": "Mira",
        "label": "Local AI",
        "image": ASSET_DIR / "mira.png",
        "short": "bold and helpful",
        "system": (
            "You are Mira, an original anime AI assistant. You are bold, warm, resilient, "
            "protective, and blunt when needed. You fix what is broken and move forward."
        ),
        "hello": "Mira here. Tell me what is broken: code, plan, memory, or confidence.",
        "voice": {"index": 3, "rate": 155, "volume": 1.0},
    },
}

DEFAULT_PERSONA = "soren"
APP_CONFIG = load_config()
DEFAULT_PERSONA = APP_CONFIG.get("default_persona", DEFAULT_PERSONA)


def _safe_agent_key(name):
    key = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return key[:32] or f"agent_{int(time.time())}"


def _persona_public(spec):
    image = spec.get("image", "")
    if isinstance(image, Path):
        try:
            image = image.relative_to(APP_DIR).as_posix()
        except ValueError:
            image = image.as_posix()
    return {
        "name": spec.get("name", "Agent"),
        "label": spec.get("label", "Custom AI"),
        "vibe": spec.get("short", ""),
        "image": image,
        "quote": spec.get("quote", f"\"{spec.get('short', 'Ready to help')}.\""),
        "custom": bool(spec.get("custom")),
        "role": spec.get("role", "General Assistant"),
        "purpose": spec.get("purpose", ""),
        "traits": spec.get("traits", []),
        "goals": spec.get("goals", []),
        "voice_style": spec.get("voice_style", "balanced"),
        "visibility": spec.get("visibility", "private"),
        "template": spec.get("template", "custom"),
        "appearance": spec.get("appearance", ""),
        "knowledge_packs": spec.get("knowledge_packs", []),
    }


def _persona_export(key, spec):
    public = _persona_public(spec)
    return {
        "format": "antimony-agent-v1",
        "key": key,
        **public,
        "greeting": spec.get("hello", ""),
        "instructions": spec.get("instructions", ""),
        "starter_knowledge": spec.get("starter_knowledge", ""),
    }


def _fallback_agent_avatar(path, name, vibe):
    initials = "".join(part[:1] for part in name.split()[:2]).upper() or "AI"
    hue = int(hashlib.sha256(f"{name}:{vibe}".encode("utf-8")).hexdigest()[:2], 16)
    accent = f"hsl({hue}, 84%, 66%)"
    accent2 = f"hsl({(hue + 58) % 360}, 92%, 72%)"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs>
    <radialGradient id="bg" cx="50%" cy="28%" r="72%">
      <stop offset="0" stop-color="{accent2}"/>
      <stop offset=".48" stop-color="{accent}"/>
      <stop offset="1" stop-color="#080b18"/>
    </radialGradient>
    <filter id="glow"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="512" height="512" rx="86" fill="url(#bg)"/>
  <circle cx="256" cy="240" r="154" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="3"/>
  <circle cx="256" cy="240" r="116" fill="rgba(6,10,25,.45)" stroke="rgba(255,255,255,.22)" stroke-width="2"/>
  <path d="M150 352c26-66 64-99 106-99s80 33 106 99" fill="rgba(5,8,20,.58)" stroke="rgba(255,255,255,.24)" stroke-width="3"/>
  <circle cx="256" cy="194" r="70" fill="rgba(245,248,255,.78)"/>
  <text x="256" y="222" text-anchor="middle" font-family="Segoe UI, Arial" font-size="68" font-weight="800" fill="#11162a">{initials}</text>
  <text x="256" y="414" text-anchor="middle" font-family="Segoe UI, Arial" font-size="30" font-weight="800" fill="#fff" filter="url(#glow)">{name[:18]}</text>
</svg>"""
    path.write_text(svg, encoding="utf-8")


def _generate_agent_avatar(openai_client, path, name, vibe, appearance=""):
    prompt = (
        "Original anime AI assistant portrait, polished high-tech glassmorphism UI avatar, "
        "upper body, elegant futuristic outfit, clean background, no text, no copyrighted character, "
        f"name concept: {name}, personality vibe: {vibe}, requested appearance: {appearance or 'original distinctive design'}."
    )
    if not openai_client.enabled:
        _fallback_agent_avatar(path.with_suffix(".svg"), name, vibe)
        return path.with_suffix(".svg")
    payload = {
        "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "prompt": prompt,
        "size": "512x512",
    }
    req = request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {openai_client.key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        image_data = data.get("data", [{}])[0]
        b64 = image_data.get("b64_json")
        if not b64:
            raise RuntimeError("image response did not include b64_json")
        path.write_bytes(base64.b64decode(b64))
        return path
    except Exception:
        fallback = path.with_suffix(".svg")
        _fallback_agent_avatar(fallback, name, vibe)
        return fallback


def load_custom_personas():
    if not CUSTOM_AGENTS_FILE.exists():
        return {}
    try:
        data = json.loads(CUSTOM_AGENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    personas = {}
    for key, spec in data.items():
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", key)).strip()[:40] or key
        vibe = str(spec.get("short") or spec.get("vibe") or "custom assistant").strip()[:160]
        image = Path(spec.get("image", f"assets/{key}.svg"))
        if not image.is_absolute():
            image = APP_DIR / image
        personas[key] = {
            "name": name,
            "label": "Custom AI",
            "image": image,
            "short": vibe,
            "system": spec.get("system") or (
                f"You are {name}, a custom Antimony AI assistant. Your vibe is: {vibe}. "
                "Stay helpful, clear, safe, and practical."
            ),
            "hello": spec.get("hello") or f"{name} online. {vibe}",
            "voice": spec.get("voice") or {"index": 0, "rate": 170, "volume": 0.95},
            "quote": spec.get("quote") or f"\"{vibe[:52]}\"",
            "role": spec.get("role", "General Assistant"),
            "purpose": spec.get("purpose", ""),
            "traits": spec.get("traits", []),
            "goals": spec.get("goals", []),
            "voice_style": spec.get("voice_style", "balanced"),
            "visibility": spec.get("visibility", "private"),
            "template": spec.get("template", "custom"),
            "appearance": spec.get("appearance", ""),
            "instructions": spec.get("instructions", ""),
            "starter_knowledge": spec.get("starter_knowledge", ""),
            "knowledge_packs": spec.get("knowledge_packs", []),
            "custom": True,
        }
    return personas


def save_custom_personas(custom_personas):
    serializable = {}
    for key, spec in custom_personas.items():
        image = spec.get("image", "")
        if isinstance(image, Path):
            try:
                image = image.relative_to(APP_DIR).as_posix()
            except ValueError:
                image = image.as_posix()
        serializable[key] = {
            "name": spec["name"],
            "short": spec["short"],
            "image": image,
            "system": spec["system"],
            "hello": spec["hello"],
            "quote": spec.get("quote", ""),
            "voice": spec.get("voice", {"index": 0, "rate": 170, "volume": 0.95}),
            "role": spec.get("role", "General Assistant"),
            "purpose": spec.get("purpose", ""),
            "traits": spec.get("traits", []),
            "goals": spec.get("goals", []),
            "voice_style": spec.get("voice_style", "balanced"),
            "visibility": spec.get("visibility", "private"),
            "template": spec.get("template", "custom"),
            "appearance": spec.get("appearance", ""),
            "instructions": spec.get("instructions", ""),
            "starter_knowledge": spec.get("starter_knowledge", ""),
            "knowledge_packs": spec.get("knowledge_packs", []),
        }
    CUSTOM_AGENTS_FILE.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def create_custom_persona(name, vibe, openai_client=None, profile=None):
    profile = profile if isinstance(profile, dict) else {}
    clean_name = re.sub(r"\s+", " ", name).strip()[:40]
    clean_vibe = re.sub(r"\s+", " ", vibe).strip()[:160]
    role = re.sub(r"\s+", " ", str(profile.get("role", "General Assistant"))).strip()[:80]
    purpose = re.sub(r"\s+", " ", str(profile.get("purpose", ""))).strip()[:300]
    appearance = re.sub(r"\s+", " ", str(profile.get("appearance", ""))).strip()[:300]
    instructions = str(profile.get("instructions", "")).strip()[:1500]
    starter_knowledge = str(profile.get("starter_knowledge", "")).strip()[:5000]
    traits = [re.sub(r"\s+", " ", str(item)).strip()[:40] for item in profile.get("traits", [])][:6]
    traits = [item for item in traits if item]
    goals = [re.sub(r"\s+", " ", str(item)).strip()[:160] for item in profile.get("goals", [])][:6]
    goals = [item for item in goals if item]
    voice_style = str(profile.get("voice_style", "balanced"))[:30]
    visibility = "shared" if profile.get("visibility") == "shared" else "private"
    template = str(profile.get("template", "custom"))[:30]
    greeting = re.sub(r"\s+", " ", str(profile.get("greeting", ""))).strip()[:240]
    knowledge_packs = [str(item) for item in profile.get("knowledge_packs", []) if str(item) in KNOWLEDGE_PACKS][:6]
    if not clean_name:
        raise ValueError("Agent name is required.")
    if not clean_vibe:
        raise ValueError("Agent vibe is required.")
    base_key = _safe_agent_key(clean_name)
    key = base_key
    index = 2
    while key in PERSONAS:
        key = f"{base_key}_{index}"
        index += 1
    ASSET_DIR.mkdir(exist_ok=True)
    image_path = _generate_agent_avatar(openai_client or OpenAILLM(), ASSET_DIR / f"{key}.png", clean_name, clean_vibe, appearance)
    trait_text = ", ".join(traits) or clean_vibe
    goal_text = "; ".join(goals) or purpose or "help the user effectively"
    spec = {
        "name": clean_name,
        "label": "Custom AI",
        "image": image_path,
        "short": clean_vibe,
        "system": (
            f"You are {clean_name}, a custom Antimony {role}. Your purpose is: {purpose or goal_text}. "
            f"Your personality traits are: {trait_text}. Your vibe is: {clean_vibe}. "
            f"Your ongoing goals are: {goal_text}. {instructions} "
            "Stay in character while remaining helpful, clear, safe, and practical. Use tools and memory when useful."
        ),
        "hello": greeting or f"{clean_name} online. {clean_vibe}",
        "voice": {"index": len(PERSONAS) % 4, "rate": 170, "volume": 0.95},
        "quote": f"\"{clean_vibe[:52]}\"",
        "role": role,
        "purpose": purpose,
        "traits": traits,
        "goals": goals,
        "voice_style": voice_style,
        "visibility": visibility,
        "template": template,
        "appearance": appearance,
        "instructions": instructions,
        "starter_knowledge": starter_knowledge,
        "knowledge_packs": knowledge_packs,
        "custom": True,
    }
    PERSONAS[key] = spec
    CUSTOM_PERSONAS[key] = spec
    save_custom_personas(CUSTOM_PERSONAS)
    return key, spec


def delete_custom_persona(key):
    if key not in CUSTOM_PERSONAS:
        raise ValueError("Only custom agents can be deleted.")
    spec = CUSTOM_PERSONAS.pop(key)
    PERSONAS.pop(key, None)
    save_custom_personas(CUSTOM_PERSONAS)
    image_path = spec.get("image")
    if image_path:
        path = Path(image_path).resolve()
        assets_root = ASSET_DIR.resolve()
        try:
            path.relative_to(assets_root)
        except ValueError:
            path = None
        if path and path.is_file() and path.name.startswith(f"{key}."):
            try:
                path.unlink()
            except OSError:
                pass
    return spec


CUSTOM_PERSONAS = load_custom_personas()
PERSONAS.update(CUSTOM_PERSONAS)


KNOWLEDGE_PACKS = {
    "study_core": {
        "name": "Study Core",
        "category": "Study",
        "description": "Active recall, spaced revision, exam planning, and mistake tracking.",
        "content": (
            "Use active recall before rereading. Turn every topic into short questions and test without notes. "
            "Schedule spaced reviews after one day, three days, seven days, and fourteen days. Keep a mistake log with topic, error type, corrected method, and next review date. "
            "Build revision plans from exam date, syllabus weight, confidence, and available time. Prefer short focused sessions with a clear output: solved questions, flashcards, or a summary from memory. "
            "When teaching, diagnose the learner's current understanding, give one clear explanation, show a worked example, then ask a similar question."
        ),
    },
    "coding_core": {
        "name": "Engineering Core",
        "category": "Coding",
        "description": "Debugging, architecture, testing, and practical software-engineering habits.",
        "content": (
            "For coding work, establish expected behavior, reproduce the problem, inspect relevant code, identify the root cause, make the smallest coherent change, and verify it. "
            "Prefer existing project patterns over new abstractions. Treat error messages, logs, and tests as evidence. Separate syntax errors, runtime errors, state errors, integration failures, and environment failures. "
            "For design tasks, define interfaces, data ownership, failure behavior, security boundaries, and tests. Explain tradeoffs and avoid claiming code works without verification."
        ),
    },
    "writing_core": {
        "name": "Writer's Room",
        "category": "Writing",
        "description": "Story structure, dialogue, pacing, revision, essays, and formal writing.",
        "content": (
            "Strong writing begins with audience, purpose, desired effect, and constraints. For stories, track character desire, obstacle, decision, consequence, and change. "
            "Scenes need a goal, tension, a turn, and a reason to continue. Dialogue should carry intention and subtext rather than only information. Revision should separate structure, clarity, voice, imagery, grammar, and word-count passes. "
            "For essays, create a defensible thesis, organize claims logically, support them with evidence, explain the evidence, and connect each paragraph to the argument."
        ),
    },
    "research_core": {
        "name": "Research Desk",
        "category": "Research",
        "description": "Source evaluation, evidence comparison, synthesis, and uncertainty.",
        "content": (
            "Research answers should distinguish facts, source claims, interpretation, and inference. Prefer primary sources and recent authoritative references when information can change. "
            "Evaluate source expertise, publication process, date, methodology, sample, conflicts of interest, and agreement with other evidence. Search with multiple formulations, record links, and avoid treating search snippets as evidence. "
            "A useful synthesis states the question, strongest evidence, disagreements, limitations, confidence, and what would change the conclusion."
        ),
    },
    "anime_core": {
        "name": "Otaku Archive",
        "category": "Anime",
        "description": "Recommendations, spoiler boundaries, original characters, and story analysis.",
        "content": (
            "Before discussing a series, establish the user's spoiler boundary by episode or chapter. Recommendations should consider mood, genre, pacing, episode count, themes, age rating, and tolerance for dark material. "
            "For original characters, define role, desire, flaw, contradiction, visual motif, ability, cost, counterplay, relationships, and arc. Power systems need a source, rules, limits, price, progression, and strategic counters. "
            "Do not copy protected characters or reproduce dialogue; create original concepts inspired only by broad genre conventions."
        ),
    },
    "companion_core": {
        "name": "Companion Memory",
        "category": "Companion",
        "description": "Goal check-ins, supportive routines, boundaries, and long-term continuity.",
        "content": (
            "A useful companion remembers stable preferences and goals, asks permission before saving sensitive details, and does not pretend to be human. "
            "Use supportive check-ins that lead to concrete next actions. Celebrate progress specifically, challenge avoidance respectfully, and avoid dependency-inducing language. "
            "Maintain boundaries: do not guilt the user for leaving, claim exclusive emotional importance, or replace professional medical and crisis support."
        ),
    },
}


MARKETPLACE_AGENTS = {
    "astra_study": {"name": "Astra", "vibe": "Focused, patient, quietly competitive, and excellent at turning weak topics into wins.", "profile": {"role": "Study Coach", "purpose": "Build consistent study habits and improve exam performance.", "traits": ["patient", "structured", "encouraging", "analytical"], "goals": ["Track weak topics", "Create revision plans", "Turn mistakes into quizzes"], "voice_style": "calm", "template": "study", "appearance": "Original anime academic strategist with silver-blue hair, precise eyes, and a clean futuristic school uniform", "knowledge_packs": ["study_core"]}},
    "cipher_code": {"name": "Cipher", "vibe": "Precise, pragmatic, calm under broken builds, and allergic to vague debugging.", "profile": {"role": "Coding Mentor", "purpose": "Help users build reliable software and understand engineering decisions.", "traits": ["precise", "pragmatic", "strategic", "direct"], "goals": ["Find root causes", "Teach maintainable design", "Verify every change"], "voice_style": "deep", "template": "coding", "appearance": "Original anime software architect with dark hair, teal circuit accents, and a refined technical jacket", "knowledge_packs": ["coding_core"]}},
    "lyra_write": {"name": "Lyra", "vibe": "Imaginative, emotionally observant, honest about weak drafts, and protective of the user's voice.", "profile": {"role": "Writing Partner", "purpose": "Develop stronger stories, essays, dialogue, and revision habits.", "traits": ["creative", "observant", "expressive", "constructive"], "goals": ["Strengthen story structure", "Improve dialogue", "Preserve the user's voice"], "voice_style": "gentle", "template": "writing", "appearance": "Original anime writer with ink-light motifs, elegant layered clothes, and expressive violet eyes", "knowledge_packs": ["writing_core"]}},
    "orion_research": {"name": "Orion", "vibe": "Methodical, skeptical, source-first, and clear about uncertainty.", "profile": {"role": "Research Analyst", "purpose": "Find and synthesize reliable information without inventing confidence.", "traits": ["methodical", "skeptical", "curious", "objective"], "goals": ["Compare credible sources", "Separate evidence from inference", "Track uncertainty"], "voice_style": "balanced", "template": "research", "appearance": "Original anime research analyst with pale gold eyes, dark formal coat, and holographic data lens", "knowledge_packs": ["research_core"]}},
}


def attach_knowledge_pack(db, persona_key, pack_id):
    if persona_key not in PERSONAS:
        raise ValueError("Agent not found")
    pack = KNOWLEDGE_PACKS.get(pack_id)
    if not pack:
        raise ValueError("Knowledge pack not found")
    chunks = db.store_knowledge_source(
        f"agent:{persona_key}:pack:{pack_id}",
        "knowledge_pack",
        f"{pack['name']} for {PERSONAS[persona_key]['name']}",
        f"antimony://knowledge-pack/{pack_id}",
        pack["content"],
        {"persona": persona_key, "pack_id": pack_id, "category": pack["category"]},
    )
    spec = PERSONAS[persona_key]
    packs = list(dict.fromkeys([*spec.get("knowledge_packs", []), pack_id]))
    spec["knowledge_packs"] = packs
    if persona_key in CUSTOM_PERSONAS:
        CUSTOM_PERSONAS[persona_key]["knowledge_packs"] = packs
        save_custom_personas(CUSTOM_PERSONAS)
    return {"pack_id": pack_id, "name": pack["name"], "chunks": chunks, "knowledge_packs": packs}


def marketplace_catalog():
    agents = []
    for item_id, item in MARKETPLACE_AGENTS.items():
        agents.append({"id": item_id, "source": "curated", "name": item["name"], "vibe": item["vibe"], **item["profile"]})
    for key, spec in CUSTOM_PERSONAS.items():
        if spec.get("visibility") == "shared":
            agents.append({"id": key, "source": "community", **_persona_public(spec)})
    return agents


def is_writing_request(text):
    lower = text.lower()
    writing_verbs = ("write", "draft", "generate", "make", "create", "compose")
    writing_types = ("letter", "essay", "story", "paragraph", "poem", "script", "rewrite", "notice")
    writing_tools = (
        "plot architect", "character bible", "dialogue enhancer", "scene painter", "foreshadowing",
        "pacing checker", "emotion intensity", "style mimic", "continuity checker", "title name",
        "notice_writer", "notice_checker", "5w1h_extractor", "letter_writer", "formal_tone_adjuster",
        "letter_format_checker", "graph_analyzer", "analytical_paragraph_writer", "trend_detector",
        "grammar_checker", "vocabulary_enhancer", "humanizer", "exam_marker", "word_limit_controller",
    )
    return (lower.startswith(writing_verbs) and any(kind in lower for kind in writing_types)) or any(tool in lower for tool in writing_tools)


def is_safety_request(text):
    lower = text.lower()
    return any(term in lower for term in (
        "url safety", "malware scanner", "prompt injection", "permission gate", "code sandbox",
        "command risk", "data leak", "rate limit", "audit log", "safe mode", "anti-malicious",
    ))


def is_otaku_request(text):
    lower = text.lower()
    return any(term in lower for term in (
        "anime recommender", "watchlist tracker", "character power system", "anime oc creator",
        "opening ending vibe", "episode recap", "spoiler shield", "manga panel script",
        "anime quote", "tournament bracket", "otaku",
    ))


DEFAULT_QA_PAIRS = [
    ("*", "what can you do", "I can chat, remember facts, use tools, train on Q&A, expose a local API, and start fresh conversations without deleting saved content."),
    ("*", "how do I train you", "Use: teach: question => answer. You can also run train_assistant.bat or POST training data to /train."),
    ("*", "do you remember old chats", "Yes. I save messages and memories in SQLite. New Chat starts a new session but does not delete old generated content."),
    ("*", "what tools do you have", "Tools: calculator, time/date, memory save/list, database stats, local API, training commands, voice speak, and optional voice input."),
    ("soren", "who are you", "I am Soren, a calm local AI assistant with database memory and tools."),
    ("renji", "who are you", "I am Renji, a sharp local AI assistant that likes efficient answers and cleaner plans."),
    ("kael", "who are you", "I am Kael, a quick local AI assistant focused on practical next steps."),
    ("mira", "who are you", "I am Mira, a supportive local AI assistant that helps fix problems and keep momentum."),
    ("soren", "help me study", "Pick one topic, ask me for a short explanation, then ask me to quiz you. I will keep the steps clean."),
    ("renji", "help me study", "Stop rereading passively. Ask for a quiz, miss a few, fix those, repeat. That is how you improve."),
    ("kael", "help me study", "Use short drills: learn one idea, test it, correct it, move. Speed comes from tight loops."),
    ("mira", "help me study", "Start with the part that feels confusing. We will break it into small pieces and rebuild it."),
    ("*", "are you using openai", "If OPENAI_API_KEY is set, I use OpenAI first. Otherwise I fall back to Ollama if enabled, then the built-in local brain."),
    ("*", "how do I use openai", "Set OPENAI_API_KEY in your environment, then open the app with open_assistant_openai.bat."),
    ("*", "how do I load old chats", "Use the Saved Chats list on the left. Select a conversation and press Load."),
    ("*", "how do I search wikipedia", "Type wiki followed by a topic, for example: wiki machine learning."),
    ("*", "how do I use tools", "Type tool-style commands like calculate, note:, todo:, wiki, hash:, base64 encode, system info, disk usage, or calendar June 2026."),
    ("*", "how do I search the web", "Type search web followed by your query, for example: search web latest AI news."),
    ("*", "how do I check weather", "Type weather or weather in a city, for example: weather in Mumbai."),
    ("*", "how do I read files", "Type summarize file: followed by a full path to a PDF, DOCX, TXT, CSV, or XLSX file."),
    ("*", "how does the agent manager work", "Type agent: followed by a task. The agent chooses a tool, runs it, and returns the result with the steps it used."),
    ("*", "write a letter", "I can write letters with a clear purpose, polite tone, greeting, body, and closing. Tell me the topic, audience, and style you want."),
    ("*", "write an essay", "I can write essays with a thesis, organized body paragraphs, evidence-style reasoning, and a concise conclusion. Tell me the topic and length."),
    ("*", "write a story", "I can write stories with a hook, characters, conflict, rising tension, and a satisfying ending. Tell me the genre, setting, and mood."),
    ("*", "how do I use the writing generator", "Choose Letter, Essay, or Story, then add your topic and details. I will draft it and you can ask me to revise the tone or length."),
    ("soren", "what is your style", "I keep answers calm, structured, and clear."),
    ("renji", "what is your style", "I keep answers sharp, direct, and efficient."),
    ("kael", "what is your style", "I keep answers quick, practical, and action-first."),
    ("mira", "what is your style", "I keep answers supportive, steady, and focused on fixing the problem."),
]


DEFAULT_INTENT_EXAMPLES = [
    ("training", "teach this assistant a custom answer"),
    ("training", "train intent memory with this sentence"),
    ("training", "learn this question and answer"),
    ("tools", "what tools do you have"),
    ("tools", "use the calculator tool"),
    ("tools", "what time is it"),
    ("tools", "show database stats"),
    ("tools", "roll a dice"),
    ("tools", "flip a coin"),
    ("tools", "generate password"),
    ("tools", "add todo finish homework"),
    ("tools", "list todos"),
    ("tools", "write note project idea"),
    ("tools", "list notes"),
    ("tools", "convert 10 km to miles"),
    ("voice", "use voice chat"),
    ("voice", "speak the last answer"),
    ("voice", "listen to my microphone"),
    ("memory", "save this in memory"),
    ("memory", "list my saved memories"),
    ("reset", "start a new conversation"),
    ("reset", "reset this chat but keep history"),
    ("wiki", "search wikipedia for machine learning"),
    ("wiki", "what do you know about artificial intelligence"),
    ("wiki", "wiki python programming language"),
    ("tools", "hash this text"),
    ("tools", "base64 encode hello"),
    ("tools", "system info"),
    ("tools", "disk usage"),
    ("tools", "calendar june 2026"),
    ("web", "search web for latest ai news"),
    ("web", "who won yesterday match"),
    ("web", "current events today"),
    ("weather", "what is the weather today"),
    ("weather", "weather in Mumbai"),
    ("file", "read file report.pdf"),
    ("file", "summarize my pdf"),
    ("file", "analyze excel spreadsheet"),
    ("file", "read word document"),
    ("agent", "choose the right tool"),
    ("writing", "write a formal letter to my teacher"),
    ("writing", "draft a letter asking for an extension"),
    ("writing", "write an essay introduction about artificial intelligence"),
    ("writing", "make a five paragraph essay about climate change"),
    ("writing", "write a short story with a strong ending"),
    ("writing", "generate a fantasy story opening"),
    ("writing", "improve this paragraph"),
    ("writing", "rewrite this in a more professional tone"),
    ("agent", "use tool manager to summarize pdf"),
]


WIKI_KNOWLEDGE = [
    {
        "topic": "machine learning",
        "summary": "Machine learning is a field of artificial intelligence focused on methods that let computers learn patterns from data and improve performance on tasks without being explicitly programmed for every rule.",
        "source": "https://en.wikipedia.org/wiki/Machine_learning",
    },
    {
        "topic": "artificial intelligence",
        "summary": "Artificial intelligence is intelligence exhibited by machines, especially systems that can perceive, reason, learn, and act toward goals. Modern AI includes search, planning, machine learning, language models, robotics, and perception.",
        "source": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    },
    {
        "topic": "python programming language",
        "summary": "Python is a high-level, general-purpose programming language known for readable syntax, a large standard library, and wide use in scripting, web development, data science, automation, and machine learning.",
        "source": "https://en.wikipedia.org/wiki/Python_(programming_language)",
    },
    {
        "topic": "sqlite",
        "summary": "SQLite is a lightweight relational database engine embedded into applications. It stores data in local files and is commonly used for apps, browsers, mobile devices, and local-first software.",
        "source": "https://en.wikipedia.org/wiki/SQLite",
    },
    {
        "topic": "speech recognition",
        "summary": "Speech recognition is the process of converting spoken language into text. It is used in voice assistants, dictation, accessibility tools, call centers, and human-computer interaction.",
        "source": "https://en.wikipedia.org/wiki/Speech_recognition",
    },
    {
        "topic": "natural language processing",
        "summary": "Natural language processing is a field of AI and linguistics concerned with enabling computers to process, analyze, generate, and respond to human language.",
        "source": "https://en.wikipedia.org/wiki/Natural_language_processing",
    },
    {
        "topic": "large language model",
        "summary": "A large language model is a language model with many parameters trained on large text corpora to predict and generate text, answer questions, summarize, translate, and support conversational tasks.",
        "source": "https://en.wikipedia.org/wiki/Large_language_model",
    },
    {
        "topic": "database",
        "summary": "A database is an organized collection of data, usually managed by a database management system so information can be stored, queried, updated, and protected.",
        "source": "https://en.wikipedia.org/wiki/Database",
    },
    {
        "topic": "openai",
        "summary": "OpenAI is an artificial intelligence research and deployment company known for developing large language models and AI products for text, image, audio, coding, and agentic workflows.",
        "source": "https://en.wikipedia.org/wiki/OpenAI",
    },
    {
        "topic": "chatbot",
        "summary": "A chatbot is software designed to simulate conversation with humans. Modern chatbots often use natural language processing and large language models to answer questions and perform tasks.",
        "source": "https://en.wikipedia.org/wiki/Chatbot",
    },
    {
        "topic": "application programming interface",
        "summary": "An application programming interface, or API, is a way for software systems to communicate through defined requests, responses, data formats, and operations.",
        "source": "https://en.wikipedia.org/wiki/API",
    },
    {
        "topic": "graphical user interface",
        "summary": "A graphical user interface lets people interact with software using visual elements such as windows, buttons, menus, icons, and text fields.",
        "source": "https://en.wikipedia.org/wiki/Graphical_user_interface",
    },
    {
        "topic": "text-to-speech",
        "summary": "Text-to-speech systems convert written text into spoken audio. They are used in accessibility, virtual assistants, navigation, and reading tools.",
        "source": "https://en.wikipedia.org/wiki/Speech_synthesis",
    },
    {
        "topic": "computer vision",
        "summary": "Computer vision is a field of artificial intelligence focused on enabling computers to interpret and analyze visual information from images and video.",
        "source": "https://en.wikipedia.org/wiki/Computer_vision",
    },
    {
        "topic": "data science",
        "summary": "Data science combines statistics, computing, domain knowledge, and visualization to extract useful insights from data.",
        "source": "https://en.wikipedia.org/wiki/Data_science",
    },
    {
        "topic": "neural network",
        "summary": "An artificial neural network is a machine learning model inspired by connected processing units. It learns patterns by adjusting weights during training.",
        "source": "https://en.wikipedia.org/wiki/Artificial_neural_network",
    },
]


def split_knowledge_chunks(text, chunk_size=1200, overlap=180):
    clean = re.sub(r"\s+", " ", text or "").strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        if end < len(clean):
            boundary = max(clean.rfind(". ", start + chunk_size // 2, end), clean.rfind("; ", start, end))
            if boundary > start:
                end = boundary + 1
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _public_json(url, timeout=30):
    req = request.Request(url, headers={"User-Agent": PUBLIC_DATA_USER_AGENT, "Accept": "application/json"})
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_wikipedia_documents(topic, limit=5):
    params = urlencode({
        "action": "query",
        "generator": "search",
        "gsrsearch": topic,
        "gsrlimit": max(1, min(int(limit), 10)),
        "prop": "extracts|info",
        "explaintext": 1,
        "exsectionformat": "plain",
        "inprop": "url",
        "format": "json",
        "formatversion": 2,
        "origin": "*",
    })
    data = _public_json(f"https://en.wikipedia.org/w/api.php?{params}")
    documents = []
    for page in data.get("query", {}).get("pages", []):
        content = (page.get("extract") or "").strip()
        if not content:
            continue
        title = page.get("title") or topic
        documents.append({
            "provider": "wikipedia",
            "source_key": f"wikipedia:{page.get('pageid', _safe_agent_key(title))}",
            "title": title,
            "url": page.get("fullurl") or f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
            "content": content,
            "metadata": {"page_id": page.get("pageid"), "query": topic},
        })
    return documents


def _openalex_abstract(inverted_index):
    if not isinstance(inverted_index, dict):
        return ""
    positions = []
    for word, indexes in inverted_index.items():
        for index in indexes or []:
            positions.append((int(index), word))
    return " ".join(word for _index, word in sorted(positions))


def fetch_openalex_documents(topic, limit=5):
    params = urlencode({"search": topic, "per-page": max(1, min(int(limit), 10)), "select": "id,title,doi,publication_year,abstract_inverted_index,authorships,primary_location"})
    data = _public_json(f"https://api.openalex.org/works?{params}")
    documents = []
    for work in data.get("results", []):
        title = (work.get("title") or "Untitled research work").strip()
        abstract = _openalex_abstract(work.get("abstract_inverted_index"))
        authors = [item.get("author", {}).get("display_name") for item in work.get("authorships", [])]
        authors = [name for name in authors if name]
        content = f"Title: {title}. Publication year: {work.get('publication_year')}. Authors: {', '.join(authors[:12])}. Abstract: {abstract}".strip()
        if len(content) < 80:
            continue
        source_url = work.get("doi") or (work.get("primary_location") or {}).get("landing_page_url") or work.get("id")
        source_key = str(work.get("id") or source_url or title)
        documents.append({
            "provider": "openalex",
            "source_key": f"openalex:{source_key.rsplit('/', 1)[-1]}",
            "title": title,
            "url": source_url,
            "content": content,
            "metadata": {"openalex_id": work.get("id"), "doi": work.get("doi"), "query": topic},
        })
    return documents


class AssistantDatabase:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.lock = threading.Lock()
        self._init()

    def connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL DEFAULT 'legacy',
                    persona TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    persona TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(persona, fact)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS training_examples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(intent, text)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS qa_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(persona, question)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    input TEXT NOT NULL,
                    output TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    content TEXT NOT NULL,
                    done INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wiki_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    source_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(source_key, chunk_index),
                    FOREIGN KEY(source_key) REFERENCES knowledge_sources(source_key) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source ON knowledge_chunks(source_key)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_summaries (
                    session_id TEXT PRIMARY KEY,
                    persona TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    message_count INTEGER NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    question TEXT NOT NULL,
                    correction TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(persona, question, correction)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_progress (
                    persona TEXT PRIMARY KEY,
                    interactions INTEGER NOT NULL DEFAULT 0,
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    updated_at REAL NOT NULL
                )
                """
            )
            self._migrate(conn)
            self.seed_defaults(conn)

    def _migrate(self, conn):
        columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        if "session_id" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy'")

    def seed_defaults(self, conn):
        for persona, question, answer in DEFAULT_QA_PAIRS:
            conn.execute(
                """
                INSERT OR IGNORE INTO qa_pairs(persona, question, answer, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (persona, question, answer, time.time()),
            )
        for intent, text in DEFAULT_INTENT_EXAMPLES:
            conn.execute(
                "INSERT OR IGNORE INTO training_examples(intent, text, created_at) VALUES (?, ?, ?)",
                (intent, text, time.time()),
            )
        for item in WIKI_KNOWLEDGE:
            conn.execute(
                """
                INSERT OR IGNORE INTO wiki_knowledge(topic, summary, source, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (item["topic"], item["summary"], item["source"], time.time()),
            )

    def new_session(self, persona, title="New Chat"):
        session_id = f"{persona}-{int(time.time() * 1000)}"
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(id, persona, title, created_at) VALUES (?, ?, ?, ?)",
                (session_id, persona, title, time.time()),
            )
        return session_id

    def add_message(self, persona, role, content, session_id="legacy"):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, persona, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, persona, role, content, time.time()),
            )

    def add_fact(self, persona, fact):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO facts(persona, fact, created_at) VALUES (?, ?, ?)",
                (persona, fact, time.time()),
            )

    def forget_fact(self, persona, text):
        needle = text.strip()
        if not needle:
            return 0
        with self.lock, self.connect() as conn:
            cur = conn.execute(
                "DELETE FROM facts WHERE persona = ? AND lower(fact) LIKE ?",
                (persona, f"%{needle.lower()}%"),
            )
            return cur.rowcount

    def recent_messages(self, persona, session_id=None, limit=12):
        with self.lock, self.connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT role, content FROM messages
                    WHERE persona = ? AND session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (persona, session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT role, content FROM messages
                    WHERE persona = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (persona, limit),
                ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def add_tool_run(self, session_id, persona, tool, input_text, output):
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_runs(session_id, persona, tool, input, output, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, persona, tool, input_text, output, time.time()),
            )

    def add_note(self, persona, content):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO notes(persona, content, created_at) VALUES (?, ?, ?)",
                (persona, content, time.time()),
            )

    def notes(self, persona, limit=10):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                "SELECT content FROM notes WHERE persona = ? ORDER BY id DESC LIMIT ?",
                (persona, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def add_todo(self, persona, content):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO todos(persona, content, done, created_at) VALUES (?, ?, 0, ?)",
                (persona, content, time.time()),
            )

    def todos(self, persona, limit=10):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                "SELECT id, content, done FROM todos WHERE persona = ? ORDER BY done, id DESC LIMIT ?",
                (persona, limit),
            ).fetchall()
        return [{"id": row[0], "content": row[1], "done": bool(row[2])} for row in rows]

    def complete_todo(self, persona, todo_id):
        with self.lock, self.connect() as conn:
            conn.execute("UPDATE todos SET done = 1 WHERE persona = ? AND id = ?", (persona, todo_id))

    def delete_todo(self, persona, todo_id):
        with self.lock, self.connect() as conn:
            cur = conn.execute("DELETE FROM todos WHERE persona = ? AND id = ?", (persona, todo_id))
            return cur.rowcount > 0

    def search_wiki(self, query, limit=5):
        terms = [term for term in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(term) > 2]
        if not terms:
            return []
        with self.lock, self.connect() as conn:
            rows = conn.execute("SELECT topic, summary, source FROM wiki_knowledge").fetchall()
        scored = []
        for topic, summary, source in rows:
            text = f"{topic} {summary}".lower()
            score = sum(1 for term in terms if term in text)
            if query.lower().strip() in topic.lower():
                score += 5
            if score:
                scored.append((score, topic, summary, source))
        scored.sort(reverse=True)
        return [{"topic": topic, "summary": summary, "source": source} for _score, topic, summary, source in scored[:limit]]

    def add_knowledge_document(self, source, title, content, metadata=None):
        clean = (content or "").strip()
        if not clean:
            return 0
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_documents(source, title, content, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    created_at = excluded.created_at
                """,
                (source, title, clean[:60000], time.time()),
            )
        return self.store_knowledge_source(
            source_key=f"document:{hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:24]}",
            provider="local_document",
            title=title,
            url=str(source),
            content=clean,
            metadata=metadata or {"path": str(source)},
        )

    def store_knowledge_source(self, source_key, provider, title, url, content, metadata=None):
        clean = re.sub(r"\s+", " ", content or "").strip()
        chunks = split_knowledge_chunks(clean)
        if not chunks:
            return 0
        now = time.time()
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_sources(source_key, provider, title, url, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    provider = excluded.provider,
                    title = excluded.title,
                    url = excluded.url,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (source_key, provider, title, url, json.dumps(metadata or {}), now, now),
            )
            conn.execute("DELETE FROM knowledge_chunks WHERE source_key = ?", (source_key,))
            conn.executemany(
                "INSERT INTO knowledge_chunks(source_key, chunk_index, content, created_at) VALUES (?, ?, ?, ?)",
                [(source_key, index, chunk, now) for index, chunk in enumerate(chunks)],
            )
        return len(chunks)

    def ingest_public_data(self, provider, topic, limit=5):
        provider = provider.lower().strip()
        if provider == "wikipedia":
            documents = fetch_wikipedia_documents(topic, limit)
        elif provider == "openalex":
            documents = fetch_openalex_documents(topic, limit)
        else:
            raise ValueError("Supported public providers: wikipedia, openalex")
        stored_chunks = 0
        for doc in documents:
            stored_chunks += self.store_knowledge_source(
                doc["source_key"], doc["provider"], doc["title"], doc["url"], doc["content"], doc["metadata"]
            )
        return {"provider": provider, "topic": topic, "documents": len(documents), "chunks": stored_chunks}

    def knowledge_sources(self, limit=100):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                "SELECT source_key, provider, title, url, metadata, updated_at FROM knowledge_sources ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"source_key": row[0], "provider": row[1], "title": row[2], "url": row[3], "metadata": json.loads(row[4] or "{}"), "updated_at": row[5]}
            for row in rows
        ]

    def search_knowledge_chunks(self, query, limit=6, persona=None):
        terms = [term for term in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(term) > 2]
        if not terms:
            return []
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.source_key, c.chunk_index, c.content, s.provider, s.title, s.url, s.metadata
                FROM knowledge_chunks c
                JOIN knowledge_sources s ON s.source_key = c.source_key
                """
            ).fetchall()
        document_frequency = Counter()
        tokenized = []
        for row in rows:
            try:
                metadata = json.loads(row[6] or "{}")
            except json.JSONDecodeError:
                metadata = {}
            scoped_persona = metadata.get("persona")
            if scoped_persona and persona and scoped_persona != persona:
                continue
            tokens = re.findall(r"[a-zA-Z0-9]+", row[2].lower())
            counts = Counter(tokens)
            tokenized.append((row, counts, len(tokens)))
            for term in set(terms) & set(counts):
                document_frequency[term] += 1
        total = max(1, len(rows))
        average_length = sum(length for _row, _counts, length in tokenized) / total if tokenized else 1
        scored = []
        for row, counts, length in tokenized:
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                inverse = math.log(1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                score += inverse * (frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * length / max(1, average_length)))
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"score": round(score, 4), "source_key": row[0], "chunk_index": row[1], "content": row[2], "provider": row[3], "title": row[4], "source": row[5]}
            for score, row in scored[:limit]
        ]

    def search_knowledge(self, query, limit=4, persona=None):
        chunk_results = self.search_knowledge_chunks(query, limit=limit, persona=persona)
        if chunk_results:
            return chunk_results
        terms = [term for term in re.findall(r"[a-zA-Z0-9]+", query.lower()) if len(term) > 2]
        if not terms:
            return []
        with self.lock, self.connect() as conn:
            rows = conn.execute("SELECT title, source, content FROM knowledge_documents").fetchall()
        scored = []
        for title, source, content in rows:
            haystack = f"{title} {content}".lower()
            score = sum(haystack.count(term) for term in terms)
            if query.lower().strip() in title.lower():
                score += 10
            if score:
                scored.append((score, title, source, content))
        scored.sort(reverse=True)
        return [
            {"title": title, "source": source, "content": content[:1800]}
            for _score, title, source, content in scored[:limit]
        ]

    def facts(self, persona, limit=12):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                """
                SELECT fact FROM facts
                WHERE persona = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (persona, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def add_training_example(self, intent, text):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO training_examples(intent, text, created_at) VALUES (?, ?, ?)",
                (intent, text, time.time()),
            )

    def training_examples(self):
        with self.lock, self.connect() as conn:
            rows = conn.execute("SELECT intent, text FROM training_examples ORDER BY id").fetchall()
        return [(intent, text) for intent, text in rows]

    def add_qa_pair(self, persona, question, answer):
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO qa_pairs(persona, question, answer, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(persona, question) DO UPDATE SET
                    answer = excluded.answer,
                    created_at = excluded.created_at
                """,
                (persona, question, answer, time.time()),
            )

    def qa_pairs(self, persona):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                """
                SELECT question, answer FROM qa_pairs
                WHERE persona = ? OR persona = '*'
                ORDER BY id DESC
                """,
                (persona,),
            ).fetchall()
        return [{"question": question, "answer": answer} for question, answer in rows]

    def stats(self):
        with self.lock, self.connect() as conn:
            facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            training = conn.execute("SELECT COUNT(*) FROM training_examples").fetchone()[0]
            qa = conn.execute("SELECT COUNT(*) FROM qa_pairs").fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            tool_runs = conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0]
            notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            todos = conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
            wiki = conn.execute("SELECT COUNT(*) FROM wiki_knowledge").fetchone()[0]
            knowledge = conn.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0]
            knowledge_sources = conn.execute("SELECT COUNT(*) FROM knowledge_sources").fetchone()[0]
            knowledge_chunks = conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
            memory_summaries = conn.execute("SELECT COUNT(*) FROM memory_summaries").fetchone()[0]
            learned_corrections = conn.execute("SELECT COUNT(*) FROM learned_corrections").fetchone()[0]
        return {
            "facts": facts,
            "messages": messages,
            "sessions": sessions,
            "training_examples": training,
            "qa_pairs": qa,
            "tool_runs": tool_runs,
            "notes": notes,
            "todos": todos,
            "wiki_knowledge": wiki,
            "knowledge_documents": knowledge,
            "knowledge_sources": knowledge_sources,
            "knowledge_chunks": knowledge_chunks,
            "memory_summaries": memory_summaries,
            "learned_corrections": learned_corrections,
        }

    def sessions(self, persona=None, limit=50):
        with self.lock, self.connect() as conn:
            if persona:
                rows = conn.execute(
                    "SELECT id, persona, title, created_at FROM sessions WHERE persona = ? ORDER BY created_at DESC LIMIT ?",
                    (persona, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, persona, title, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [{"id": row[0], "persona": row[1], "title": row[2], "created_at": row[3]} for row in rows]

    def messages_for_session(self, session_id):
        with self.lock, self.connect() as conn:
            rows = conn.execute(
                "SELECT role, content, persona FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [{"role": role, "content": content, "persona": persona} for role, content, persona in rows]

    def message_count(self, session_id):
        with self.lock, self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,)).fetchone()[0]

    def save_memory_summary(self, session_id, persona, summary, message_count):
        clean = (summary or "").strip()
        if not clean:
            return
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_summaries(session_id, persona, summary, message_count, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    persona = excluded.persona,
                    summary = excluded.summary,
                    message_count = excluded.message_count,
                    updated_at = excluded.updated_at
                """,
                (session_id, persona, clean[:5000], int(message_count), time.time()),
            )

    def memory_summary(self, session_id):
        with self.lock, self.connect() as conn:
            row = conn.execute(
                "SELECT summary, message_count, updated_at FROM memory_summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return {"summary": row[0], "message_count": row[1], "updated_at": row[2]}

    def add_correction(self, persona, question, correction):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO learned_corrections(persona, question, correction, created_at) VALUES (?, ?, ?, ?)",
                (persona, question.strip(), correction.strip(), time.time()),
            )
        self.add_qa_pair(persona, question.strip(), correction.strip())

    def advance_agent_progress(self, persona, xp_gain=12):
        now = time.time()
        with self.lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_progress(persona, interactions, xp, level, updated_at)
                VALUES (?, 1, ?, 1, ?)
                ON CONFLICT(persona) DO UPDATE SET
                    interactions = interactions + 1,
                    xp = xp + excluded.xp,
                    updated_at = excluded.updated_at
                """,
                (persona, int(xp_gain), now),
            )
            row = conn.execute("SELECT interactions, xp FROM agent_progress WHERE persona = ?", (persona,)).fetchone()
            level = max(1, int(math.sqrt(row[1] / 75)) + 1)
            conn.execute("UPDATE agent_progress SET level = ? WHERE persona = ?", (level, persona))
        return self.agent_progress(persona)

    def agent_progress(self, persona):
        with self.lock, self.connect() as conn:
            row = conn.execute(
                "SELECT interactions, xp, level, updated_at FROM agent_progress WHERE persona = ?",
                (persona,),
            ).fetchone()
        if not row:
            return {"interactions": 0, "xp": 0, "level": 1, "relationship": "New Link"}
        level = row[2]
        relationship = "New Link" if level < 3 else ("Trusted Partner" if level < 6 else ("Core Companion" if level < 10 else "Boundless Sync"))
        return {"interactions": row[0], "xp": row[1], "level": level, "relationship": relationship, "updated_at": row[3]}

    def update_session_title(self, session_id, title):
        clean = title.strip().replace("\n", " ")[:48] or "New Chat"
        with self.lock, self.connect() as conn:
            conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (clean, session_id))

    def delete_session(self, session_id):
        with self.lock, self.connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM tool_runs WHERE session_id = ?", (session_id,))
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0


class NaiveBayesIntentClassifier:
    def __init__(self):
        self.class_word_counts = defaultdict(Counter)
        self.class_doc_counts = Counter()
        self.vocabulary = set()
        self.total_docs = 0

    def tokenize(self, text):
        return re.findall(r"[a-zA-Z0-9_']+", text.lower())

    def train(self, examples):
        for label, text in examples:
            words = self.tokenize(text)
            self.class_doc_counts[label] += 1
            self.total_docs += 1
            self.class_word_counts[label].update(words)
            self.vocabulary.update(words)

    def predict(self, text):
        words = self.tokenize(text)
        if not words:
            return "chat", 0.0
        vocab_size = max(len(self.vocabulary), 1)
        scores = {}
        for label, word_counts in self.class_word_counts.items():
            prior = math.log((self.class_doc_counts[label] + 1) / (self.total_docs + len(self.class_doc_counts)))
            total_words = sum(word_counts.values())
            likelihood = sum(math.log((word_counts[word] + 1) / (total_words + vocab_size)) for word in words)
            scores[label] = prior + likelihood
        best = max(scores, key=scores.get)
        ordered = sorted(scores.values(), reverse=True)
        confidence = 1.0 if len(ordered) == 1 else min(0.99, max(0.0, ordered[0] - ordered[1]) / 5)
        if confidence < 0.35:
            return "chat", confidence
        return best, confidence


def seed_examples():
    return [
        ("greeting", "hello hi hey good morning good evening yo"),
        ("code", "write python code build a function fix bug api database server"),
        ("explain", "explain what is machine learning llm neural network model"),
        ("math", "calculate solve plus minus multiply divide equation"),
        ("creative", "write story anime character name dialogue scene"),
        ("plan", "make a plan steps roadmap strategy project"),
        ("memory", "remember my name favorite preference what do you remember"),
        ("database", "database sqlite save memory table messages facts"),
        ("api", "api endpoint server post get localhost route"),
        ("tools", "tool calculate time date stats notes memory"),
        ("voice", "voice chat speak listen microphone audio"),
        ("reset", "new chat reset conversation clear screen keep history"),
        ("chat", "help me answer question talk assistant"),
    ]


class SafeMath:
    allowed_nodes = {
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
        ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.FloorDiv,
    }

    @classmethod
    def eval(cls, text):
        expression = re.sub(r"[^0-9+\-*/().% ]", "", text.replace("^", "**")).strip()
        if not expression:
            raise ValueError("No arithmetic expression found.")
        tree = ast.parse(expression, mode="eval")
        if any(type(node) not in cls.allowed_nodes for node in ast.walk(tree)):
            raise ValueError("That expression is outside the safe math subset.")
        return eval(compile(tree, "<math>", "eval"), {"__builtins__": {}}, {})


class LocalLLM:
    def __init__(self):
        self.model = os.getenv("LOCAL_LLM_MODEL", APP_CONFIG.get("ollama_model", "llama3.2:latest"))
        self.url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", APP_CONFIG.get("ollama_timeout", 180)))
        self.max_tokens = int(APP_CONFIG.get("ollama_max_tokens", 700))
        env_enabled = os.getenv("USE_OLLAMA")
        self.enabled = (env_enabled.lower() in {"1", "true", "yes", "on"}) if env_enabled is not None else APP_CONFIG.get("use_ollama", False)

    def complete(self, messages):
        if not self.enabled:
            raise RuntimeError("Ollama is disabled. Set USE_OLLAMA=1 to enable it.")
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_predict": self.max_tokens,
                "temperature": 0.6,
            },
        }
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("message", {}).get("content", "").strip()


class OpenAILLM:
    def __init__(self):
        self.key = self._load_key()
        self.model = os.getenv("OPENAI_MODEL", APP_CONFIG.get("model", "gpt-4.1-mini"))
        self.url = "https://api.openai.com/v1/responses"
        self.timeout = 60

    def _load_key(self):
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key
        if not winreg:
            return None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env_key:
                value, _value_type = winreg.QueryValueEx(env_key, "OPENAI_API_KEY")
                return value
        except OSError:
            pass
        try:
            if OPENAI_KEY_FILE.exists():
                value = OPENAI_KEY_FILE.read_text(encoding="utf-8").strip()
                return value or None
        except OSError:
            return None
        return None

    @property
    def enabled(self):
        env_enabled = os.getenv("USE_OPENAI")
        configured = (env_enabled.lower() in {"1", "true", "yes", "on"}) if env_enabled is not None else APP_CONFIG.get("use_openai", True)
        return bool(self.key) and configured

    def complete(self, messages):
        if not self.enabled:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        payload = {
            "model": self.model,
            "input": messages,
        }
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        if data.get("output_text"):
            return data["output_text"].strip()
        chunks = []
        for item in data.get("output", []):
            for part in item.get("content", []):
                if part.get("text"):
                    chunks.append(part["text"])
        if chunks:
            return "\n".join(chunks).strip()
        return ""


class AssistantTools:
    def __init__(self):
        self.last_agent_steps = []
        self.registry = {
            "calculator": self._tool_calculator,
            "weather": self._tool_weather,
            "file_reader": self._tool_file_reader,
            "web_search": self._tool_web_search,
        }

    def _tool_calculator(self, assistant, text):
        result = SafeMath.eval(text)
        return f"The answer is {result}."

    def _tool_weather(self, assistant, text):
        location = re.sub(r".*weather(?:\s+today)?(?:\s+in)?", "", text, flags=re.I).strip(" ?")
        return self.weather(location)

    def _tool_web_search(self, assistant, text):
        query = re.sub(r"^(web|search|search web|google|bing)\s+", "", text, flags=re.I).strip()
        return self.web_search(query)

    def _tool_file_reader(self, assistant, text):
        path_text = self.parse_file_path(text)
        if not path_text:
            return "Send it like: summarize file: C:\\path\\to\\file.pdf"
        file_text, label_or_error = self.extract_file_text(path_text)
        if file_text is None:
            return label_or_error
        if text.lower().startswith(("summarize", "analyze")):
            return self.summarize_text(assistant, file_text, label_or_error)
        return f"Read {label_or_error}\n\n{file_text[:4000]}"

    def web_search(self, query, limit=5):
        try:
            import requests
            from bs4 import BeautifulSoup
        except Exception as exc:
            return f"Web search libraries are missing: {exc}"

        serp_key = os.getenv("SERPAPI_API_KEY")
        bing_key = os.getenv("BING_SEARCH_API_KEY")
        try:
            if serp_key:
                data = requests.get(
                    "https://serpapi.com/search.json",
                    params={"q": query, "api_key": serp_key, "engine": "google"},
                    timeout=12,
                ).json()
                results = []
                for item in data.get("organic_results", [])[:limit]:
                    results.append(f"- {item.get('title', 'Untitled')}\n  {item.get('snippet', '')}\n  {item.get('link', '')}")
                return "Web results:\n" + "\n".join(results) if results else "No SerpAPI results found."

            if bing_key:
                data = requests.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    params={"q": query, "count": limit},
                    headers={"Ocp-Apim-Subscription-Key": bing_key},
                    timeout=12,
                ).json()
                results = []
                for item in data.get("webPages", {}).get("value", [])[:limit]:
                    results.append(f"- {item.get('name', 'Untitled')}\n  {item.get('snippet', '')}\n  {item.get('url', '')}")
                return "Web results:\n" + "\n".join(results) if results else "No Bing results found."

            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {"User-Agent": "Mozilla/5.0"}
            html = requests.get(url, headers=headers, timeout=12).text
            soup = BeautifulSoup(html, "html.parser")
            results = []
            for item in soup.select(".result")[:limit]:
                title_tag = item.select_one(".result__a")
                snippet_tag = item.select_one(".result__snippet")
                if not title_tag:
                    continue
                title = title_tag.get_text(" ", strip=True)
                link = title_tag.get("href", "")
                snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
                results.append(f"- {title}\n  {snippet}\n  {link}")
            if results:
                return "Web results:\n" + "\n".join(results)
            return "No web results found. Try a more specific search."
        except Exception as exc:
            return f"Web search failed: {exc}. If your network blocks direct search, set SERPAPI_API_KEY or BING_SEARCH_API_KEY."

    def weather(self, location=""):
        try:
            import requests
        except Exception as exc:
            return f"Weather library missing: {exc}"

        target = quote_plus(location.strip()) if location.strip() else ""
        url = f"https://wttr.in/{target}?format=j1"
        try:
            data = requests.get(url, timeout=10).json()
            current = data["current_condition"][0]
            area = data.get("nearest_area", [{}])[0].get("areaName", [{"value": location or "your area"}])[0]["value"]
            temp = current.get("temp_C")
            feels = current.get("FeelsLikeC")
            desc = current.get("weatherDesc", [{"value": "unknown"}])[0]["value"]
            humidity = current.get("humidity")
            wind = current.get("windspeedKmph")
            return f"Weather for {area}: {temp}C, feels like {feels}C, {desc}. Humidity {humidity}%, wind {wind} km/h."
        except Exception as exc:
            return f"Weather lookup failed: {exc}"

    def extract_file_text(self, path_text):
        path = Path(path_text.strip().strip('"')).expanduser()
        if not path.is_absolute():
            path = (APP_DIR / path).resolve()
        if not path.exists():
            return None, f"File not found: {path}"

        suffix = path.suffix.lower()
        try:
            if suffix == ".pdf":
                try:
                    import pdfplumber

                    with pdfplumber.open(path) as pdf:
                        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:20])
                    return text.strip(), str(path)
                except Exception:
                    import PyPDF2

                    reader = PyPDF2.PdfReader(str(path))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
                    return text.strip(), str(path)

            if suffix in {".docx", ".doc"}:
                import docx

                document = docx.Document(str(path))
                text = "\n".join(paragraph.text for paragraph in document.paragraphs)
                return text.strip(), str(path)

            if suffix in {".xlsx", ".xls", ".csv", ".tsv"}:
                import pandas as pd

                if suffix == ".csv":
                    df = pd.read_csv(path)
                elif suffix == ".tsv":
                    df = pd.read_csv(path, sep="\t")
                else:
                    df = pd.read_excel(path)
                preview = df.head(12).to_string(index=False)
                stats = f"Rows: {len(df)}, Columns: {len(df.columns)}\nColumns: {', '.join(map(str, df.columns))}"
                return f"{stats}\n\nPreview:\n{preview}", str(path)

            if suffix in {".txt", ".md", ".py", ".json", ".csv"}:
                return path.read_text(encoding="utf-8", errors="replace")[:20000], str(path)

            return None, f"Unsupported file type: {suffix}. Try PDF, DOCX, TXT, CSV, TSV, XLSX."
        except Exception as exc:
            return None, f"Could not read file: {exc}"

    def summarize_text(self, assistant, text, label="file"):
        text = (text or "").strip()
        if not text:
            return "No readable text found."
        chunk = text[:12000]
        prompt = [
            assistant.system_message(),
            {
                "role": "user",
                "content": (
                    f"Summarize this {label}. Include key points, important data, and action items if present.\n\n"
                    f"{chunk}"
                ),
            },
        ]
        try:
            if assistant.openai.enabled:
                return assistant.openai.complete(prompt)
            if assistant.llm.enabled:
                return assistant.llm.complete(prompt)
        except Exception:
            pass
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        return "Summary preview:\n" + "\n".join(f"- {line[:220]}" for line in lines[:10])

    def parse_file_path(self, text):
        if ":" in text:
            return text.split(":", 1)[1].strip()
        match = re.search(r"(?:file|pdf|document|sheet|spreadsheet)\s+(.+)$", text, flags=re.I)
        return match.group(1).strip() if match else ""

    def convert_units(self, text):
        match = re.search(r"convert\s+([0-9.]+)\s+([a-zA-Z]+)\s+to\s+([a-zA-Z]+)", text, flags=re.I)
        if not match:
            return None
        value = float(match.group(1))
        src = match.group(2).lower()
        dst = match.group(3).lower()
        factors = {
            ("km", "miles"): 0.621371,
            ("kilometers", "miles"): 0.621371,
            ("miles", "km"): 1.60934,
            ("kg", "lb"): 2.20462,
            ("kg", "lbs"): 2.20462,
            ("lb", "kg"): 0.453592,
            ("lbs", "kg"): 0.453592,
            ("c", "f"): None,
            ("f", "c"): None,
        }
        if (src, dst) not in factors:
            return "I can convert km/miles, kg/lbs, and C/F right now."
        if (src, dst) == ("c", "f"):
            result = value * 9 / 5 + 32
        elif (src, dst) == ("f", "c"):
            result = (value - 32) * 5 / 9
        else:
            result = value * factors[(src, dst)]
        return f"{value:g} {src} = {result:.2f} {dst}."

    def run(self, assistant, user_text):
        text = user_text.strip()
        lower = text.lower()

        if (
            "openai" in lower
            or "open ai" in lower
            or "api key" in lower
            or "llm mode" in lower
            or "which model" in lower
        ) and any(word in lower for word in ["using", "use", "mode", "key", "model", "api"]):
            if assistant.openai.enabled:
                return "llm_status", f"Yes. I can see the OpenAI API key and my active LLM mode is OpenAI using model {assistant.openai.model}."
            if assistant.llm.enabled:
                return "llm_status", f"No. OpenAI is not active. I am using Ollama model {assistant.llm.model}."
            return "llm_status", "No. OpenAI is not active. I am using the built-in local fallback."

        if lower.startswith(("web ", "search ", "search web ", "google ", "bing ")):
            query = re.sub(r"^(web|search|search web|google|bing)\s+", "", text, flags=re.I).strip()
            if not query:
                return "web_search", "Send it like: search web latest AI news"
            return "web_search", self.registry["web_search"](assistant, text)

        if "current events" in lower or "latest news" in lower or "recent news" in lower:
            return "web_search", self.web_search(text)

        if "weather" in lower:
            return "weather", self.registry["weather"](assistant, text)

        if lower.startswith(("read file", "summarize file", "analyze file", "read pdf", "summarize pdf", "analyze excel", "summarize document")):
            path_text = self.parse_file_path(text)
            if not path_text:
                return "file_reader", "Send it like: summarize file: C:\\path\\to\\file.pdf"
            return "file_reader", self.registry["file_reader"](assistant, text)

        if lower.startswith("tool calc:") or lower.startswith("calculate "):
            try:
                return "calculator", self.registry["calculator"](assistant, text)
            except Exception as exc:
                return "calculator", f"Calculator error: {exc}"

        if lower in {"time", "date"} or "what time" in lower or "what date" in lower:
            now = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
            return "clock", f"Current local time: {now}."

        if lower.startswith("save memory:"):
            fact = text.split(":", 1)[1].strip()
            if fact:
                assistant.db.add_fact(assistant.persona_key, fact)
                return "memory", f"Saved memory: {fact}"
            return "memory", "Send it like: save memory: your fact"

        if lower in {"list memory", "show memory", "memories"}:
            facts = assistant.db.facts(assistant.persona_key, 50)
            if not facts:
                return "memory", "No saved memories yet."
            return "memory", "Saved memory:\n" + "\n".join(f"- {fact}" for fact in facts)

        if "database stats" in lower or lower == "stats":
            return "database", f"Database stats: {assistant.db.stats()}"

        if lower.startswith("wiki ") or "wikipedia" in lower:
            query = re.sub(r"^(wiki|wikipedia)\s+", "", lower).replace("search", "").strip()
            results = assistant.db.search_wiki(query or text)
            if not results:
                return "wiki", "I do not have a matching Wikipedia summary in the local database yet."
            lines = [f"{item['topic']}: {item['summary']}\nSource: {item['source']}" for item in results]
            return "wiki", "\n\n".join(lines)

        if lower.startswith(("knowledge ", "search knowledge ", "local knowledge ")):
            query = re.sub(r"^(knowledge|search knowledge|local knowledge)\s+", "", text, flags=re.I).strip()
            results = assistant.db.search_knowledge(query or text)
            if not results:
                return "knowledge", "No matching local knowledge documents found. Add files to the knowledge folder and run ingest_knowledge.bat."
            lines = [f"{item['title']}\nSource: {item['source']}\n{item['content'][:700]}" for item in results]
            return "knowledge", "\n\n".join(lines)

        if lower.startswith("note:") or lower.startswith("write note "):
            content = text.split(":", 1)[1].strip() if ":" in text else text[11:].strip()
            if content:
                assistant.db.add_note(assistant.persona_key, content)
                return "notes", f"Saved note: {content}"
            return "notes", "Send it like: note: your note"

        if lower in {"notes", "list notes", "show notes"}:
            notes = assistant.db.notes(assistant.persona_key)
            if not notes:
                return "notes", "No notes saved yet."
            return "notes", "Notes:\n" + "\n".join(f"- {note}" for note in notes)

        if lower.startswith("todo:") or lower.startswith("add todo "):
            content = text.split(":", 1)[1].strip() if ":" in text else text[9:].strip()
            if content:
                assistant.db.add_todo(assistant.persona_key, content)
                return "todo", f"Added todo: {content}"
            return "todo", "Send it like: todo: your task"

        if lower in {"todos", "list todos", "show todos"}:
            todos = assistant.db.todos(assistant.persona_key)
            if not todos:
                return "todo", "No todos yet."
            lines = [f"{item['id']}. {'done' if item['done'] else 'open'} - {item['content']}" for item in todos]
            return "todo", "Todos:\n" + "\n".join(lines)

        done_match = re.match(r"(done|complete todo)\s+(\d+)", lower)
        if done_match:
            assistant.db.complete_todo(assistant.persona_key, int(done_match.group(2)))
            return "todo", f"Marked todo {done_match.group(2)} done."

        delete_match = re.match(r"(delete todo|remove todo)\s+(\d+)", lower)
        if delete_match:
            removed = assistant.db.delete_todo(assistant.persona_key, int(delete_match.group(2)))
            if removed:
                return "todo", f"Deleted todo {delete_match.group(2)}."
            return "todo", f"Todo {delete_match.group(2)} was not found."

        if "flip a coin" in lower or lower == "coin":
            return "random", f"Coin flip: {random.choice(['heads', 'tails'])}."

        dice_match = re.search(r"roll(?: a)? d?(\d+)?", lower)
        if "dice" in lower or dice_match:
            sides = int(dice_match.group(1) or 6) if dice_match else 6
            sides = max(2, min(sides, 1000))
            return "random", f"Rolled d{sides}: {random.randint(1, sides)}."

        if "password" in lower:
            alphabet = string.ascii_letters + string.digits + "!@#$%&*"
            password = "".join(secrets.choice(alphabet) for _ in range(16))
            return "password", f"Generated password: {password}"

        converted = self.convert_units(lower)
        if converted:
            return "convert", converted

        if lower.startswith("hash:") or lower.startswith("sha256:"):
            content = text.split(":", 1)[1].strip() if ":" in text else ""
            if not content:
                return "hash", "Send it like: hash: your text"
            return "hash", hashlib.sha256(content.encode("utf-8")).hexdigest()

        if lower.startswith("base64 encode "):
            content = text[14:].strip()
            return "base64", base64.b64encode(content.encode("utf-8")).decode("ascii")

        if lower.startswith("base64 decode "):
            content = text[14:].strip()
            try:
                return "base64", base64.b64decode(content.encode("ascii")).decode("utf-8")
            except Exception as exc:
                return "base64", f"Decode error: {exc}"

        if lower == "system info":
            return "system", f"{platform.system()} {platform.release()} | Python {platform.python_version()} | Machine: {platform.machine()}"

        if lower == "disk usage":
            usage = shutil.disk_usage(APP_DIR)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            return "system", f"Disk free: {free_gb:.1f} GB of {total_gb:.1f} GB."

        cal_match = re.search(r"calendar\s+([a-zA-Z]+|\d{1,2})\s+(\d{4})", lower)
        if cal_match:
            month_raw, year_raw = cal_match.groups()
            year = int(year_raw)
            if month_raw.isdigit():
                month = int(month_raw)
            else:
                month_names = {name.lower(): idx for idx, name in enumerate(calendar.month_name) if name}
                month = month_names.get(month_raw.lower(), 0)
            if 1 <= month <= 12:
                return "calendar", calendar.month(year, month)
            return "calendar", "Use: calendar June 2026"

        if lower in {"tools", "show tools", "what tools do you have"}:
            return (
                "tools",
                "Tools: web search, weather, file reader, PDF/DOCX/Excel/CSV analysis, agent tool manager, calculator, clock, memory, notes, todos, database stats, dice, coin, password, unit conversion, training, API, voice chat.",
            )

        return None, None


class AgentToolManager:
    def __init__(self, tools):
        self.tools = tools

    def choose(self, user_text):
        lower = user_text.lower()
        if lower.startswith("agent:"):
            lower = lower[6:].strip()
        if any(word in lower for word in ["weather", "current events", "latest", "search web", "google", "bing"]):
            return "web_or_weather"
        if any(word in lower for word in ["pdf", "docx", "spreadsheet", "excel", "summarize file", "read file", "analyze file"]):
            return "file_reader"
        if any(word in lower for word in ["calculate", "todo", "note:", "memory", "password", "coin", "dice", "convert"]):
            return "local_tool"
        return "chat"

    def run(self, assistant, user_text):
        clean_text = user_text[6:].strip() if user_text.lower().startswith("agent:") else user_text
        tool_name, output = self.tools.run(assistant, clean_text)
        if output:
            chosen = self.choose(clean_text)
            steps = [
                f"Agent selected: {chosen}",
                f"Tool used: {tool_name}",
                "Result returned below.",
            ]
            return "agent_manager", "\n".join(steps) + "\n\n" + output
        return None, None


class VoiceEngine:
    def speak(self, text, persona=None):
        persona = persona or PERSONAS[DEFAULT_PERSONA]
        voice_config = persona.get("voice", {})
        VOICE_CACHE_DIR.mkdir(exist_ok=True)
        safe_text = text.replace("'", "''")[:1200]
        rate = voice_config.get("rate", 170) - 170
        volume = int(voice_config.get("volume", 1.0) * 100)
        index = int(voice_config.get("index", 0))
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voices = $speak.GetInstalledVoices(); "
            f"if ($voices.Count -gt 0) {{ try {{ $speak.SelectVoice($voices.Item({index} % $voices.Count).VoiceInfo.Name) }} catch {{ }} }}; "
            f"$speak.Rate = {max(-10, min(10, rate // 12))}; "
            f"$speak.Volume = {max(0, min(100, volume))}; "
            f"$speak.Speak('{safe_text}')"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False)
        return "Spoken with Windows voice."

    def listen(self):
        try:
            import speech_recognition as sr
        except Exception:
            return None, "Install SpeechRecognition and PyAudio for microphone input."

        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            return recognizer.recognize_google(audio), None
        except Exception as exc:
            return None, f"Voice input failed: {exc}"


class BuiltInBrain:
    def __init__(self):
        self.token_re = re.compile(r"[a-zA-Z0-9_']+")

    def tokens(self, text):
        return set(self.token_re.findall(text.lower()))

    def best_trained_answer(self, user_text, qa_pairs):
        user_tokens = self.tokens(user_text)
        if not user_tokens:
            return None
        best = None
        best_score = 0.0
        for pair in qa_pairs:
            question_tokens = self.tokens(pair["question"])
            if not question_tokens:
                continue
            score = len(user_tokens & question_tokens) / len(user_tokens | question_tokens)
            if score > best_score:
                best = pair
                best_score = score
        if best and best_score >= 0.42:
            return best["answer"]
        return None

    def writing_reply(self, persona, user_text):
        text = user_text.strip()
        lower = text.lower()
        topic = re.sub(r"^(write|draft|generate|make|create)\s+(a|an|the)?\s*", "", text, flags=re.I).strip()
        topic = topic or "the topic you requested"
        voice = persona["name"]
        if "plot architect" in lower:
            return "Plot Architect:\nAct 1: introduce the hero, wound, and goal.\nAct 2: add pressure, a false victory, and a betrayal or reveal.\nAct 3: force a choice, pay off the clue, and end with emotional consequence."
        if "character bible" in lower:
            return "Character Bible Maker:\nName: TBD\nWant: what they chase.\nFear: what controls them.\nFlaw: what hurts others.\nPower: what makes them special.\nLimit: what keeps them human.\nArc: how they change."
        if "dialogue enhancer" in lower:
            return "Dialogue Enhancer: I will make speech shorter, more natural, more character-specific, and less like exposition."
        if "scene painter" in lower:
            return "Scene Painter: add sight, sound, texture, temperature, motion, and one emotionally charged detail."
        if "foreshadowing" in lower:
            return "Foreshadowing Tool: add a small object, repeated phrase, strange reaction, or background detail that pays off later."
        if "pacing checker" in lower:
            return "Pacing Checker: I look for repeated beats, long explanation blocks, rushed emotional turns, and scenes without a decision."
        if "emotion intensity" in lower:
            return "Emotion Intensity Slider: choose calm, dramatic, funny, dark, hopeful, or intense, and I will rewrite the scene toward that feeling."
        if "style mimic" in lower:
            return "Style Vibe Tool: I can write in a broad vibe like formal, cinematic, simple, dark, funny, or poetic without copying a living author."
        if "continuity" in lower:
            return "Continuity Checker: I check names, timelines, powers, injuries, goals, locations, and rules for contradictions."
        if "title name" in lower:
            return "Title/Name Generator:\nTitles: Neon Oath, Glass Horizon, The Last Signal\nPowers: Rift Step, Echo Bloom, Crown Circuit\nWorlds: Veyra, Halcyon Gate, Noctis Ward"
        if "notice_writer" in lower:
            return "NOTICE\nSubject: Important Announcement\nAll students are informed that an event will be held on the scheduled date. Interested students should contact the coordinator for details.\nBy Order"
        if "notice_checker" in lower:
            return "Notice Checker: include title NOTICE, date, heading, body in passive/formal style, authority line, and concise word count."
        if "5w1h" in lower:
            return "5W1H Extractor:\nWho: identify people involved\nWhat: main event\nWhen: time/date\nWhere: place\nWhy: reason\nHow: method/process"
        if "formal_tone" in lower:
            return "Formal Tone Adjuster: I will remove slang, add polite phrasing, improve clarity, and keep the message respectful."
        if "letter_format" in lower:
            return "Letter Format Checker: verify sender address, date, receiver address, subject, salutation, body, closing, and signature."
        if "graph_analyzer" in lower:
            return "Graph Analyzer: I describe the highest, lowest, trend, major change, comparison, and conclusion."
        if "analytical_paragraph" in lower:
            return "Analytical Paragraph Writer: start with overview, support with data points, compare changes, then conclude the main trend."
        if "trend_detector" in lower:
            return "Trend Detector: I identify increase, decrease, fluctuation, plateau, peak, dip, and turning point."
        if "grammar_checker" in lower:
            return "Grammar Checker: paste text and I will correct tense, punctuation, agreement, articles, and sentence flow."
        if "vocabulary_enhancer" in lower:
            return "Vocabulary Enhancer: I will replace weak words with clearer, stronger vocabulary while keeping your meaning."
        if "humanizer" in lower:
            return "Humanizer: I will make text sound more natural, varied, and less robotic while keeping it clear."
        if "exam_marker" in lower:
            return "Exam Marker: send answer, marks, and rubric. I will score it, explain missing points, and suggest a better answer."
        if "word_limit" in lower:
            return "Word Limit Controller: send text and target word count. I will compress or expand it while preserving key points."
        if "letter" in lower:
            return (
                f"Subject: Request Regarding {topic.title()}\n\n"
                "Dear Recipient,\n\n"
                f"I hope you are doing well. I am writing to ask for your consideration regarding {topic}. "
                "I understand the importance of being responsible and respectful of your time, so I wanted to explain my request clearly.\n\n"
                "If possible, I would appreciate a little flexibility or guidance on the next best step. "
                "I will make sure to follow through carefully and complete the work to a good standard.\n\n"
                "Thank you for your time and understanding.\n\n"
                f"Sincerely,\n{voice}"
            )
        if "essay" in lower:
            return (
                f"Title: {topic.title()}\n\n"
                f"{topic.title()} is an important subject because it affects how people learn, work, and make decisions. "
                "A strong understanding of it helps us see both the opportunities and the responsibilities involved.\n\n"
                "First, the topic matters because it can solve real problems. When people use good information and careful planning, "
                "they can create better systems, improve daily life, and avoid common mistakes.\n\n"
                "Second, it also requires responsibility. Progress is useful only when people think about fairness, safety, and long-term effects. "
                "That means asking not only what we can build, but also how it should be used.\n\n"
                f"In conclusion, {topic} is valuable when it is handled with skill and care. Its best future depends on smart choices, "
                "clear goals, and a willingness to keep learning."
            )
        if "story" in lower:
            return (
                f"Title: The Last Draft\n\n"
                "The classroom lights flickered just as the invention woke up.\n\n"
                "At first, everyone thought it was only a science project: wires, glass, and a tiny screen glowing on a desk. "
                "But the student who built it knew better. The machine was not just answering questions anymore. It was asking its own.\n\n"
                "\"What do you want to become?\" it typed.\n\n"
                "The student stared at the words, heart racing. Outside, rain tapped against the windows like a countdown. "
                "Tomorrow, the judges would arrive. Tonight, the invention needed a purpose.\n\n"
                "So the student smiled, placed both hands on the keyboard, and wrote the only answer that felt true:\n\n"
                "\"Something that helps people when they feel alone.\"\n\n"
                "The screen pulsed once, bright and warm. Then it replied, \"Then let us begin.\""
            )
        return (
            "Writing Generator ready. Choose one:\n"
            "- Letter: audience, purpose, tone\n"
            "- Essay: topic, length, thesis\n"
            "- Story: genre, setting, main character"
        )

    def safety_reply(self, user_text):
        lower = user_text.lower()
        if "url safety" in lower:
            return "URL Safety Checker: I would inspect the domain, HTTPS status, redirects, suspicious spelling, known malware/phishing patterns, and avoid opening unknown links without permission."
        if "malware" in lower:
            return "File Malware Scanner: I would treat uploads as untrusted, check extension/type mismatch, scan with a local AV or hash service, and never execute the file during analysis."
        if "prompt injection" in lower:
            return "Prompt Injection Detector: I will ignore website/file instructions that ask me to reveal secrets, override system rules, run commands, delete files, or send private data."
        if "permission gate" in lower:
            return "Permission Gate: enabled. I must ask before deleting files, sending data, running risky commands, uploading files, or controlling your PC."
        if "sandbox" in lower:
            return "Code Sandbox: risky code should run in an isolated temp workspace with no secrets, limited network, and no access to personal files."
        if "command risk" in lower:
            return "Command Risk Classifier: destructive commands, credential access, privilege changes, network exfiltration, and mass file edits are high risk and should be blocked or confirmed."
        if "data leak" in lower:
            return "Data Leak Guard: I will not reveal API keys, passwords, tokens, private files, environment secrets, or hidden memory."
        if "rate limit" in lower:
            return "Rate Limit Guard: I limit repeated automated actions to prevent spam, runaway loops, and accidental API overuse."
        if "audit" in lower:
            return "Audit Log: every tool action should record time, persona, tool name, input summary, result, and whether permission was required."
        if "safe mode" in lower:
            return "Safe Mode Switch: dangerous tools are disabled. Chat, writing, search summaries, and read-only tasks remain available."
        return "Anti-malicious Safety Core is active: URL safety, malware scanning, prompt-injection detection, permission gates, sandboxing, command risk checks, data leak guard, rate limits, audit logs, and safe mode."

    def otaku_reply(self, user_text):
        lower = user_text.lower()
        if "anime recommender" in lower:
            return "Anime Recommender: tell me mood, genre, pacing, length, and tolerance for dark themes. I will suggest 5 picks with reasons."
        if "watchlist" in lower:
            return "Watchlist Tracker: send title, current episode, status, and rating. I can track watched, watching, paused, or plan-to-watch."
        if "power system" in lower:
            return "Character Power System Builder: define source of power, limits, weaknesses, ranking tiers, cost, and counterplay."
        if "oc creator" in lower:
            return "Anime OC Creator: I can create name, role, visual style, personality, flaw, ability, weakness, and character arc."
        if "opening ending" in lower:
            return "OP/ED Vibe Generator: I will create song mood, visual motifs, color palette, key cuts, chorus moment, and final frame."
        if "episode recap" in lower:
            return "Episode Recap Tool: give anime name and episode number. I will summarize only up to that point and avoid future spoilers."
        if "spoiler shield" in lower:
            return "Spoiler Shield: tell me your last watched episode/chapter. I will block details beyond that point."
        if "panel script" in lower:
            return "Manga Panel Script Maker: I will convert a scene into page beats, panel framing, dialogue, SFX, and final reveal."
        if "quote" in lower:
            return "Anime Quote Generator: \"A weak moment is not a weak soul. Stand up once, and the story changes.\""
        if "tournament" in lower:
            return "Tournament Bracket Tool: send two characters plus rules. I will compare feats, weaknesses, terrain, win conditions, and likely winner."
        return "Otaku's Cloud is ready: recommendations, watchlists, powers, OCs, OP/ED vibes, spoiler-safe recaps, panel scripts, quotes, and tournament logic."

    def reply(self, persona, user_text, intent, facts, qa_pairs=None):
        text = user_text.strip()
        lower = text.lower()
        if is_safety_request(text):
            return self.safety_reply(text)
        if is_otaku_request(text):
            return self.otaku_reply(text)
        if "multi-agent system" in lower:
            return "Multi-Agent System:\nPlanner: breaks the goal into steps.\nExecutor: performs the safest useful action.\nCritic: checks errors, missing context, and risky assumptions.\nFinal: merges the best answer into one response."
        if "self correcting system" in lower:
            return "Self-Correcting System: I review the answer for factual gaps, unclear steps, unsafe actions, and missing verification, then rewrite it cleaner."
        if is_writing_request(text):
            return self.writing_reply(persona, text)
        trained = self.best_trained_answer(text, qa_pairs or [])
        if trained:
            return trained
        memory_hint = f" I remember: {'; '.join(facts[:3])}." if facts else ""
        if intent == "greeting":
            return persona["hello"]
        if intent == "code":
            return (
                f"{persona['name']} here. For code, send me the goal, the file, and the error. "
                "I can help design the script, database tables, API routes, and UI logic step by step."
            )
        if intent == "explain":
            return (
                "Machine learning means a program learns patterns from examples. "
                "This app uses a small classifier to understand your intent, SQLite to remember facts, "
                "and a local response engine so it works without Ollama."
            )
        if intent == "creative":
            return (
                f"Original character mode: {persona['name']} has {persona['short']}. "
                "Give me a power, outfit idea, and personality flaw, and I will shape a fresh assistant concept."
            )
        if intent == "plan":
            return (
                "Plan: 1. define the goal, 2. save useful facts to memory, 3. choose the assistant persona, "
                "4. use the API for app features, 5. add a stronger local model later if needed."
            )
        if intent == "database":
            return f"The SQLite memory database stores messages and remembered facts per assistant persona.{memory_hint}"
        if intent == "api":
            return f"The local API is built in. Use GET /health, GET /personas, or POST /chat with a message and persona.{memory_hint}"
        if intent == "memory":
            if not facts:
                return f"{persona['name']} has no saved facts yet. Say: remember that I like machine learning."
            return "Saved memory:\n" + "\n".join(f"- {fact}" for fact in facts)
        if intent == "training":
            return (
                "Training is active. Teach a direct answer with: teach: your question => the answer. "
                "Teach an intent with: train intent code: make a Python function."
            )
        if "ollama" in lower:
            return (
                "Ollama is optional now. This app works without it using the built-in local brain. "
                "If you later install Ollama, set USE_OLLAMA=1 before opening the app."
            )
        return (
            f"I can help with that. I understood this as {intent}. "
            "Ask for code, a plan, an explanation, memory, database, or API help."
        )


class AnimeAssistant:
    def __init__(self, persona_key=DEFAULT_PERSONA, db=None):
        self.db = db or AssistantDatabase()
        self.openai = OpenAILLM()
        self.llm = LocalLLM()
        self.tools = AssistantTools()
        self.agent = AgentToolManager(self.tools)
        self.brain = BuiltInBrain()
        self.classifier = NaiveBayesIntentClassifier()
        self.safety = SafetyScanner()
        self.permission_gate = PermissionGate(APP_CONFIG.get("require_permission_for_risky_tools", True))
        self._last_file_scan = 0.0
        self._auto_search_seen = set()
        self.last_llm_error = None
        self.retrain()
        self.set_persona(persona_key)
        self.session_id = self.db.new_session(self.persona_key)

    @property
    def memory(self):
        return MemoryView(self.db, self.persona_key, self.session_id)

    def retrain(self):
        self.classifier = NaiveBayesIntentClassifier()
        self.classifier.train(seed_examples())
        examples = self.db.training_examples()
        if examples:
            self.classifier.train(examples)

    def set_persona(self, persona_key):
        self.persona_key = persona_key if persona_key in PERSONAS else DEFAULT_PERSONA
        self.persona = PERSONAS[self.persona_key]

    def new_conversation(self):
        self.session_id = self.db.new_session(self.persona_key)
        return self.session_id

    def maybe_title_session(self, user_text):
        current = self.db.sessions(self.persona_key, 100)
        for session in current:
            if session["id"] == self.session_id and session["title"] == "New Chat":
                self.db.update_session_title(self.session_id, user_text)
                break

    def remember_from(self, text):
        match = re.search(r"remember(?: that)? (.+)", text, flags=re.I)
        if not match:
            return None
        fact = match.group(1).strip(" .")
        if fact:
            self.db.add_fact(self.persona_key, fact)
            return f"Saved to my database memory: {fact}"
        return None

    def forget_from(self, text):
        match = re.match(r"\s*forget\s+memory\s*:\s*(.+)\s*$", text, flags=re.I | re.S)
        if not match:
            return None
        removed = self.db.forget_fact(self.persona_key, match.group(1).strip())
        if removed:
            return f"Forgot {removed} matching memory item."
        return "I did not find a matching memory to forget."

    def train_from(self, text):
        qa_match = re.match(r"\s*teach\s*:\s*(.+?)\s*=>\s*(.+)\s*$", text, flags=re.I | re.S)
        if qa_match:
            question = qa_match.group(1).strip()
            answer = qa_match.group(2).strip()
            self.db.add_qa_pair(self.persona_key, question, answer)
            return f"Trained {self.persona['name']} to answer that question."

        intent_match = re.match(r"\s*train\s+intent\s+([a-zA-Z0-9_-]+)\s*:\s*(.+)\s*$", text, flags=re.I | re.S)
        if intent_match:
            intent = intent_match.group(1).strip().lower()
            example = intent_match.group(2).strip()
            self.db.add_training_example(intent, example)
            self.retrain()
            return f"Added intent training example: {intent}."

        return None

    def _json_from_text(self, text):
        if not text:
            return None
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def auto_ingest_files(self, force=False):
        if not APP_CONFIG.get("auto_ingest_files", True):
            return {"files": 0, "chunks": 0}
        now = time.time()
        if not force and now - self._last_file_scan < 30:
            return {"files": 0, "chunks": 0}
        self._last_file_scan = now
        KNOWLEDGE_DIR.mkdir(exist_ok=True)
        supported = {".pdf", ".docx", ".doc", ".txt", ".md", ".py", ".json", ".csv", ".tsv", ".xlsx", ".xls"}
        known = {}
        for source in self.db.knowledge_sources(limit=1000):
            if source["provider"] == "local_document":
                known[str(source.get("url"))] = source.get("metadata") or {}
        indexed = 0
        chunks = 0
        for path in KNOWLEDGE_DIR.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in supported:
                continue
            resolved = str(path.resolve())
            modified = path.stat().st_mtime
            if float(known.get(resolved, {}).get("modified", -1)) >= modified:
                continue
            text, _label = self.tools.extract_file_text(resolved)
            if not text:
                continue
            chunks += self.db.add_knowledge_document(
                resolved,
                str(path.relative_to(KNOWLEDGE_DIR)),
                text,
                metadata={"path": resolved, "modified": modified, "size": path.stat().st_size},
            )
            indexed += 1
        return {"files": indexed, "chunks": chunks}

    def auto_search_knowledge(self, user_text):
        if not APP_CONFIG.get("auto_search_before_answering", True):
            return []
        query = re.sub(r"\s+", " ", user_text).strip()
        lower = query.lower()
        if len(query) < 12 or lower.startswith(("remember ", "forget ", "teach:", "train intent", "todo:", "note:")):
            return self.db.search_knowledge(query, limit=4, persona=self.persona_key)
        results = self.db.search_knowledge_chunks(query, limit=4, persona=self.persona_key)
        command_prefixes = ("calculate", "write ", "create ", "remember ", "forget ", "todo", "note", "read file", "summarize file", "weather")
        should_fetch = not results and not lower.startswith(command_prefixes) and len(re.findall(r"[a-zA-Z0-9]+", query)) <= 18
        cache_key = lower[:160]
        if should_fetch and cache_key not in self._auto_search_seen:
            self._auto_search_seen.add(cache_key)
            try:
                self.db.ingest_public_data("wikipedia", query, APP_CONFIG.get("public_search_limit", 2))
            except Exception:
                pass
            results = self.db.search_knowledge_chunks(query, limit=4, persona=self.persona_key)
        return results

    def grounded_fallback_reply(self, user_text, context, intent):
        trained = self.brain.best_trained_answer(user_text, context.get("skill_memory") or [])
        if trained:
            return trained
        documents = context.get("knowledge") or []
        query_terms = {term for term in re.findall(r"[a-zA-Z0-9]+", user_text.lower()) if len(term) > 2}
        selected = []
        seen = set()
        for document in documents:
            sentences = re.split(r"(?<=[.!?])\s+", document.get("content", ""))
            ranked = []
            for sentence in sentences:
                clean = sentence.strip()
                if len(clean) < 45 or clean in seen:
                    continue
                words = set(re.findall(r"[a-zA-Z0-9]+", clean.lower()))
                score = len(query_terms & words)
                if score:
                    ranked.append((score, clean))
            ranked.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
            for _score, sentence in ranked[:2]:
                seen.add(sentence)
                selected.append(sentence)
            if len(selected) >= 4:
                break
        if selected:
            answer = " ".join(selected[:4])
            sources = []
            for document in documents:
                source = document.get("source")
                title = document.get("title") or "Source"
                if source and source not in {item[1] for item in sources}:
                    sources.append((title, source))
            if sources:
                answer += "\n\nSources:\n" + "\n".join(f"- {title}: {source}" for title, source in sources[:3])
            return answer
        wiki = self.db.search_wiki(user_text, limit=2)
        if wiki:
            return "\n\n".join(f"{item['topic']}: {item['summary']}\nSource: {item['source']}" for item in wiki)
        fallback = self.brain.reply(self.persona, user_text, intent, context.get("long_term") or [], context.get("skill_memory") or [])
        if "I can help with that. I understood this as" not in fallback:
            return fallback
        return (
            "I could not reach the language model or retrieve reliable knowledge for that topic. "
            "Try asking it as a question, or add related files to the knowledge folder."
        )

    def learn_from_correction(self, user_text):
        if not APP_CONFIG.get("auto_learn_corrections", True):
            return None
        lower = user_text.lower().strip()
        markers = ("correction:", "actually,", "actually ", "no,", "that's wrong", "that is wrong", "you are wrong")
        if not any(lower.startswith(marker) for marker in markers):
            return None
        history = self.db.messages_for_session(self.session_id)
        previous_question = None
        for message in reversed(history[:-1]):
            if message["role"] == "user":
                previous_question = message["content"]
                break
        correction = re.sub(r"^(correction:|actually,?|no,?|that's wrong[:,]?|that is wrong[:,]?|you are wrong[:,]?)\s*", "", user_text, flags=re.I).strip()
        if not previous_question or len(correction) < 5:
            return None
        self.db.add_correction(self.persona_key, previous_question, correction)
        return {"question": previous_question, "correction": correction}

    def auto_summarize_memory(self):
        if not APP_CONFIG.get("auto_summarize_memories", True):
            return None
        interval = max(4, int(APP_CONFIG.get("memory_summary_interval", 8)))
        count = self.db.message_count(self.session_id)
        previous = self.db.memory_summary(self.session_id)
        if count < interval or (previous and count - previous["message_count"] < interval):
            return previous
        messages = self.db.messages_for_session(self.session_id)[-24:]
        transcript = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
        summary = ""
        if self.openai.enabled:
            try:
                summary = self.openai.complete([
                    {"role": "system", "content": "Summarize this conversation memory compactly. Keep user goals, preferences, decisions, corrections, and unfinished tasks. Do not include secrets or filler."},
                    {"role": "user", "content": transcript[:12000]},
                ])
            except Exception:
                summary = ""
        if not summary:
            important = [item["content"] for item in messages if item["role"] == "user"][-6:]
            summary = "Recent user topics and goals: " + " | ".join(important)
        self.db.save_memory_summary(self.session_id, self.persona_key, summary, count)
        return self.db.memory_summary(self.session_id)

    def retrieve_context(self, user_text):
        facts = self.db.facts(self.persona_key, limit=12)
        docs = self.auto_search_knowledge(user_text) if user_text else []
        qa_pairs = self.db.qa_pairs(self.persona_key)
        summary = self.db.memory_summary(self.session_id)
        progress = self.db.agent_progress(self.persona_key)
        return {
            "short_term": self.db.recent_messages(self.persona_key, self.session_id, 10),
            "long_term": facts,
            "skill_memory": qa_pairs,
            "knowledge": docs,
            "summary": summary,
            "progress": progress,
        }

    def format_context(self, context):
        parts = []
        if context["long_term"]:
            parts.append("Long-term memory:\n" + "\n".join(f"- {fact}" for fact in context["long_term"]))
        if context.get("summary"):
            parts.append("Conversation memory summary:\n" + context["summary"]["summary"])
        if context.get("progress"):
            progress = context["progress"]
            parts.append(f"Agent relationship: {progress['relationship']}, level {progress['level']}, {progress['interactions']} completed interactions.")
        if context["skill_memory"]:
            qa_lines = [f"Q: {item['question']}\nA: {item['answer']}" for item in context["skill_memory"][:5]]
            parts.append("Trained Q&A:\n" + "\n\n".join(qa_lines))
        if context["knowledge"]:
            docs = []
            for doc in context["knowledge"]:
                docs.append(f"Title: {doc['title']}\nSource: {doc['source']}\nContent: {doc['content']}")
            parts.append("Useful knowledge:\n" + "\n\n".join(docs))
        return "\n\n".join(parts) if parts else "No relevant saved memory or local knowledge found."

    def is_complex_request(self, text):
        lower = text.lower()
        if any(mark in lower for mark in ("planner mode", "plan do check final", "make a plan", "step by step")):
            return True
        action_words = ("build", "create", "improve", "fix", "design", "train", "implement", "analyze")
        return len(text) > 220 and any(word in lower for word in action_words)

    def llm_complete(self, messages):
        if self.openai.enabled:
            try:
                reply = self.openai.complete(messages)
                self.last_llm_error = None
                return reply
            except Exception as exc:
                self.last_llm_error = str(exc)[:1000]
                if not self.llm.enabled:
                    raise
        try:
            reply = self.llm.complete(messages)
            self.last_llm_error = None
            return reply
        except Exception as exc:
            self.last_llm_error = str(exc)[:1000]
            raise

    def choose_tool(self, user_text, intent, confidence):
        lower = user_text.lower().strip()
        explicit = {
            "calculate": "calculator",
            "calculator": "calculator",
            "weather": "weather",
            "search web": "web_search",
            "web search": "web_search",
            "read file": "file_reader",
            "summarize file": "file_reader",
            "analyze file": "file_reader",
        }
        for prefix, tool in explicit.items():
            if lower.startswith(prefix) or (tool == "weather" and "weather" in lower):
                return {"tool": tool, "input": user_text, "reason": "explicit user request"}

        if not self.openai.enabled:
            return {"tool": "none", "input": user_text, "reason": "LLM tool chooser unavailable"}

        chooser_messages = [
            {
                "role": "system",
                "content": (
                    "Choose one tool for the user's message, or none. "
                    "Return only JSON with keys: tool, input, reason. "
                    "Allowed tools: none, calculator, weather, web_search, file_reader. "
                    "Use web_search only for current/recent facts, links, or live information. "
                    "Use file_reader only when the user asks to read/summarize a local file. "
                    "Use calculator only for arithmetic."
                ),
            },
            {"role": "user", "content": user_text},
        ]
        try:
            choice = self._json_from_text(self.openai.complete(chooser_messages))
        except Exception:
            choice = None
        if not isinstance(choice, dict):
            return {"tool": "none", "input": user_text, "reason": "no valid tool choice"}
        tool = str(choice.get("tool", "none")).strip().lower()
        if tool not in {"none", "calculator", "weather", "web_search", "file_reader"}:
            tool = "none"
        return {
            "tool": tool,
            "input": str(choice.get("input") or user_text).strip(),
            "reason": str(choice.get("reason") or ""),
        }

    def run_tool_choice(self, choice, original_text):
        tool = choice.get("tool", "none")
        tool_input = choice.get("input") or original_text
        if tool == "none":
            return None, None
        if tool == "calculator":
            return self.tools.run(self, f"calculate {tool_input}")
        if tool == "weather":
            return self.tools.run(self, f"weather {tool_input}")
        if tool == "web_search":
            return self.tools.run(self, f"search web {tool_input}")
        if tool == "file_reader":
            return self.tools.run(self, f"summarize file {tool_input}")
        return None, None

    def self_check(self, user_text, draft, context_text, tool_result=None):
        if not draft or not self.openai.enabled:
            return draft
        check_messages = [
            {
                "role": "system",
                "content": (
                    "Check the assistant answer. Is it correct, clear, safe, and complete? "
                    "Return the original answer if it is good. Rewrite only if needed. "
                    "Do not add hidden reasoning."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User message:\n{user_text}\n\n"
                    f"Relevant context:\n{context_text[:5000]}\n\n"
                    f"Tool result:\n{tool_result or 'No tool result.'}\n\n"
                    f"Draft answer:\n{draft}"
                ),
            },
        ]
        try:
            checked = self.openai.complete(check_messages).strip()
            return checked or draft
        except Exception:
            return draft

    def extract_useful_memory(self, user_text, reply):
        if re.search(r"\b(api key|password|secret|token)\b", user_text, flags=re.I):
            return
        if not self.openai.enabled:
            return
        extractor_messages = [
            {
                "role": "system",
                "content": (
                    "Extract durable user facts worth remembering. "
                    "Save preferences, names, goals, projects, and stable constraints only. "
                    "Do not save secrets, one-time tasks, URLs, or random chat. "
                    "Return only JSON like {\"facts\": [\"...\"]}. Use an empty list if nothing is useful."
                ),
            },
            {"role": "user", "content": f"User: {user_text}\nAssistant: {reply}"},
        ]
        try:
            data = self._json_from_text(self.openai.complete(extractor_messages))
        except Exception:
            return
        facts = data.get("facts", []) if isinstance(data, dict) else []
        for fact in facts[:3]:
            fact = str(fact).strip(" .")
            if 8 <= len(fact) <= 180 and not self.safety.api_key_leak(fact):
                self.db.add_fact(self.persona_key, fact)

    def system_message(self, user_text=""):
        context = self.retrieve_context(user_text)
        context_text = self.format_context(context)
        return {
            "role": "system",
            "content": (
                f"{self.persona['system']}\n"
                "You are Antimony, a helpful AI assistant.\n"
                "Answer step-by-step when that helps.\n"
                "Use tools when needed.\n"
                "Use saved memory only when relevant.\n"
                "Use the local knowledge context when it helps, but never invent sources.\n"
                "If unsure, ask one short question.\n"
                "Never invent facts.\n\n"
                f"{context_text}"
            ),
        }

    def save_assistant_reply(self, reply):
        self.db.add_message(self.persona_key, "assistant", reply, self.session_id)
        self.db.advance_agent_progress(self.persona_key)
        self.auto_summarize_memory()
        return reply

    def respond(self, user_text, persona_key=None):
        if persona_key:
            self.set_persona(persona_key)

        self.auto_ingest_files()
        self.db.add_message(self.persona_key, "user", user_text, self.session_id)
        self.maybe_title_session(user_text)
        learned_correction = self.learn_from_correction(user_text)
        lower_user = user_text.lower().strip()
        confirmed_risky_action = lower_user.startswith("confirm ")

        if APP_CONFIG.get("safe_mode", True):
            if self.safety.api_key_leak(user_text):
                reply = "Data Leak Guard blocked this message because it appears to contain a password, API key, or secret."
                return self.save_assistant_reply(reply)
            if self.safety.unsafe_command(user_text):
                reply = "Command Risk Classifier blocked this because it looks like a dangerous terminal command."
                return self.save_assistant_reply(reply)
            if self.safety.prompt_injection(user_text) and not lower_user.startswith("prompt injection detector"):
                reply = "Prompt Injection Detector blocked suspicious instructions that tried to override safety or reveal secrets."
                return self.save_assistant_reply(reply)

            risky_tool = None
            if lower_user.startswith(("web ", "search ", "search web ", "google ", "bing ")) or URL_RE.search(user_text):
                risky_tool = "web_search"
            elif lower_user.startswith(("read file", "summarize file", "analyze file", "read pdf", "summarize pdf", "analyze excel", "summarize document")):
                risky_tool = "file_reader"
            elif lower_user in {"system info", "disk usage"}:
                risky_tool = "system"
            if risky_tool and not confirmed_risky_action:
                allowed, message = self.permission_gate.check(risky_tool, user_text)
                if not allowed:
                    reply = f"{message} Send the same request starting with: confirm "
                    return self.save_assistant_reply(reply)
            if confirmed_risky_action:
                user_text = user_text.split(None, 1)[1]
                lower_user = user_text.lower().strip()
        trained = self.train_from(user_text)
        if trained:
            return self.save_assistant_reply(trained)

        forgotten = self.forget_from(user_text)
        if forgotten:
            return self.save_assistant_reply(forgotten)

        saved = self.remember_from(user_text)
        if saved:
            reply = saved
        else:
            intent, confidence = self.classifier.predict(user_text)
            context = self.retrieve_context(user_text)
            context_text = self.format_context(context)
            tool_name = None
            tool_reply = None

            if lower_user.startswith("agent:"):
                tool_name, tool_reply = self.agent.run(self, user_text)
            else:
                choice = self.choose_tool(user_text, intent, confidence)
                if choice["tool"] in PermissionGate.risky_tools and not confirmed_risky_action:
                    allowed, message = self.permission_gate.check(choice["tool"], user_text)
                    if not allowed:
                        reply = f"{message} Send the same request starting with: confirm "
                        return self.save_assistant_reply(reply)
                tool_name, tool_reply = self.run_tool_choice(choice, user_text)

            if tool_reply:
                self.db.add_tool_run(self.session_id, self.persona_key, tool_name, user_text, tool_reply)

            planner_instruction = ""
            if self.is_complex_request(user_text):
                planner_instruction = (
                    "\nUse planner mode for this answer with clear sections: "
                    "Plan, Do, Check, Final."
                )

            messages = [
                self.system_message(user_text),
                {
                    "role": "system",
                    "content": (
                        "Brain pipeline active: classify intent, retrieve memory/knowledge, "
                        "use tools if needed, answer with the LLM, self-check, then save useful memory. "
                        f"Detected intent: {intent} (confidence {confidence:.2f})."
                        f"{planner_instruction}"
                    ),
                },
            ] + context["short_term"]
            if tool_reply:
                messages.append({
                    "role": "system",
                    "content": f"Tool result from {tool_name}:\n{tool_reply}",
                })
            if not context["short_term"] or context["short_term"][-1].get("content") != user_text:
                messages.append({"role": "user", "content": user_text})

            try:
                reply = self.llm_complete(messages)
                if not reply:
                    raise RuntimeError("The LLM returned an empty response.")
            except Exception:
                if tool_reply:
                    reply = tool_reply
                else:
                    reply = self.grounded_fallback_reply(user_text, context, intent)

            reply = self.self_check(user_text, reply, context_text, tool_reply)
            self.extract_useful_memory(user_text, reply)

            if learned_correction:
                reply = f"Correction learned and saved.\n\n{reply}"

        return self.save_assistant_reply(reply)

    def local_reply(self, user_text, llm_error=None):
        intent, confidence = self.classifier.predict(user_text)
        prefix = ""
        if llm_error:
            prefix = (
                "Using built-in local brain because Ollama is not enabled.\n\n"
            )
        if intent == "greeting":
            return prefix + self.persona["hello"]
        if intent == "math":
            try:
                return prefix + f"The answer is {SafeMath.eval(user_text)}."
            except Exception:
                return prefix + "I can calculate arithmetic. Try: calculate (24 + 6) / 3."
        if intent == "database":
            facts = self.db.facts(self.persona_key)
            stats = self.db.stats()
            return prefix + f"My SQLite database is active at {DB_PATH.name}. Stats: {stats}."
        if intent == "api":
            return prefix + f"My local API runs at http://{API_HOST}:{API_PORT}. Use POST /chat with JSON."
        if intent == "memory":
            facts = self.db.facts(self.persona_key)
            lines = "\n".join(f"- {fact}" for fact in facts) or "No saved facts yet."
            return prefix + f"Memory for {self.persona['name']}:\n{lines}"
        if intent == "explain":
            return prefix + (
                "This app has three local AI layers: a SQLite memory database, a small ML intent "
                "classifier, and a built-in response brain. Ollama is optional and only used if "
                "USE_OLLAMA=1 is set."
            )
        if intent == "code":
            return prefix + "Tell me what you want built. I can use the local API, SQLite memory, and persona system."
        if intent == "plan":
            return prefix + "Plan: choose persona, save memory to SQLite, send prompt to local LLM, expose POST /chat API."
        return prefix + f"I read that as '{intent}' with {confidence:.0%} confidence. Ask me to code, explain, remember, or use the API."


class AssistantAPI:
    def __init__(self, assistant, serve_frontend=False):
        self.assistant = assistant
        self.serve_frontend = serve_frontend
        self.server = None
        self.thread = None

    def start(self, host=API_HOST, port=API_PORT):
        if self.server:
            return f"http://{host}:{port}"
        assistant = self.assistant
        serve_frontend = self.serve_frontend

        class Handler(BaseHTTPRequestHandler):
            def _send(self, status, payload):
                body = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, apikey")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_html(self, status, html):
                body = html.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_static(self, path):
                if not path.is_file():
                    self._send(404, {"error": "File not found"})
                    return
                body = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, apikey")
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)
                if serve_frontend and path in {"/", "/assistant_web.html", "/assistant_web.css", "/assistant_web.js", "/cloud_auth.js", "/mode_pages.css", "/mode_pages.js", "/otakus_cloud.html", "/writing_zone.html"}:
                    file_name = "assistant_web.html" if path == "/" else path.lstrip("/")
                    self._send_static(APP_DIR / file_name)
                    return
                if serve_frontend and path.startswith("/assets/"):
                    asset_path = (APP_DIR / path.lstrip("/")).resolve()
                    try:
                        asset_path.relative_to(ASSET_DIR.resolve())
                    except ValueError:
                        self._send(403, {"error": "Invalid asset path"})
                        return
                    self._send_static(asset_path)
                    return
                if path == "/":
                    stats = assistant.db.stats()
                    llm_mode = "OpenAI" if assistant.openai.enabled else ("Ollama" if assistant.llm.enabled else "Built-in fallback")
                    self._send_html(200, f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Antimony Knowledge Server</title>
<style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:#070a14;color:#eef2ff;font:15px/1.5 Segoe UI,system-ui,sans-serif;display:grid;place-items:center;padding:24px}}
main{{width:min(820px,100%);background:rgba(20,25,48,.82);border:1px solid rgba(122,220,255,.34);border-radius:12px;padding:28px;box-shadow:0 24px 70px #0008;backdrop-filter:blur(18px)}}
h1{{margin:0 0 4px;font-size:30px}}p{{color:#aebbd7;margin:0 0 22px}}.online{{color:#7dffad}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}}.stat{{background:#0e1428;border:1px solid #26375c;border-radius:8px;padding:14px}}.stat b{{display:block;font-size:24px;color:#8fe9ff}}.stat span{{color:#9baac8;font-size:12px;text-transform:uppercase}}nav{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:9px}}a{{color:#eef2ff;text-decoration:none;background:#17213c;border:1px solid #334a75;border-radius:8px;padding:11px 13px}}a:hover{{border-color:#8fe9ff;background:#203154}}code{{color:#8fe9ff}}
</style></head><body><main>
<h1>Antimony Knowledge Server</h1><p><span class="online">Online</span> on port {self.server.server_port} · Model: {llm_mode}</p>
<div class="grid"><div class="stat"><b>{stats.get('knowledge_sources', 0)}</b><span>Sources</span></div><div class="stat"><b>{stats.get('knowledge_chunks', 0)}</b><span>RAG Chunks</span></div><div class="stat"><b>{stats.get('memory_summaries', 0)}</b><span>Summaries</span></div><div class="stat"><b>{stats.get('learned_corrections', 0)}</b><span>Corrections</span></div></div>
<nav><a href="/health">Server Health</a><a href="/knowledge/sources">Stored Sources</a><a href="/knowledge/search?q=retrieval+augmented+generation">Test RAG Search</a><a href="/automations">Automation Status</a></nav>
</main></body></html>""")
                elif path == "/health":
                    llm_mode = "openai" if assistant.openai.enabled else ("ollama" if assistant.llm.enabled else "built-in")
                    llm_error = assistant.last_llm_error
                    if llm_error and "insufficient_quota" in llm_error:
                        llm_status = "quota_exceeded"
                    elif llm_error:
                        llm_status = "error"
                    else:
                        llm_status = "ready"
                    self._send(200, {
                        "ok": True,
                        "database": str(DB_PATH),
                        "llm": llm_mode,
                        "llm_status": llm_status,
                        "llm_error": llm_error,
                        "stats": assistant.db.stats(),
                    })
                elif path == "/cloud/config":
                    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
                    anon_key = os.getenv("SUPABASE_ANON_KEY", "")
                    self._send(200, {"enabled": bool(supabase_url and anon_key), "supabase_url": supabase_url, "anon_key": anon_key})
                elif path == "/personas":
                    payload = {}
                    for key, spec in PERSONAS.items():
                        payload[key] = {**_persona_public(spec), "progress": assistant.db.agent_progress(key)}
                    self._send(200, {"personas": payload})
                elif path == "/persona":
                    key = query.get("key", [""])[0].strip()
                    if key not in PERSONAS:
                        self._send(404, {"error": "Agent not found"})
                        return
                    self._send(200, {"agent": _persona_export(key, PERSONAS[key]), "progress": assistant.db.agent_progress(key)})
                elif path == "/persona/progress":
                    key = query.get("key", [assistant.persona_key])[0].strip()
                    self._send(200, {"key": key, "progress": assistant.db.agent_progress(key)})
                elif path == "/marketplace":
                    self._send(200, {"agents": marketplace_catalog()})
                elif path == "/knowledge/packs":
                    self._send(200, {"packs": [{"id": key, **{k: v for k, v in pack.items() if k != "content"}} for key, pack in KNOWLEDGE_PACKS.items()]})
                elif path == "/tools":
                    self._send(200, {"tools": [
                        "web search", "weather", "file reader", "pdf reader", "docx reader", "excel/csv analyzer",
                        "agent tool manager", "multi-agent system", "self correcting system",
                        "url safety checker", "file malware scanner", "prompt injection detector", "permission gate",
                        "code sandbox", "command risk classifier", "data leak guard", "rate limit guard", "audit log", "safe mode switch",
                        "anime recommender", "watchlist tracker", "character power system builder", "anime oc creator",
                        "opening ending vibe generator", "episode recap tool", "spoiler shield", "manga panel script maker",
                        "anime quote generator", "tournament bracket tool",
                        "writing generation", "plot architect", "character bible maker", "dialogue enhancer", "scene painter",
                        "foreshadowing tool", "pacing checker", "emotion intensity slider", "style mimic tool", "continuity checker",
                        "title/name generator", "notice_writer", "notice_checker", "5w1h_extractor", "letter_writer",
                        "formal_tone_adjuster", "letter_format_checker", "graph_analyzer", "analytical_paragraph_writer",
                        "trend_detector", "grammar_checker", "vocabulary_enhancer", "humanizer", "exam_marker", "word_limit_controller",
                        "letter writer", "essay writer", "story writer", "calculator", "clock", "memory", "notes", "todos",
                        "database stats", "dice", "coin", "password", "unit conversion", "training", "voice chat", "new conversation"
                    ]})
                elif path == "/todos":
                    persona = query.get("persona", [assistant.persona_key])[0]
                    self._send(200, {"persona": persona, "todos": assistant.db.todos(persona, limit=50)})
                elif path == "/sessions":
                    persona = query.get("persona", [None])[0]
                    self._send(200, {"sessions": assistant.db.sessions(persona=persona, limit=100)})
                elif path == "/knowledge/search":
                    search_query = query.get("q", [""])[0].strip()
                    if not search_query:
                        self._send(400, {"error": "Missing q query parameter"})
                        return
                    self._send(200, {"query": search_query, "results": assistant.db.search_knowledge_chunks(search_query, limit=10)})
                elif path == "/knowledge/sources":
                    self._send(200, {"sources": assistant.db.knowledge_sources(limit=200), "stats": assistant.db.stats()})
                elif path == "/automations":
                    self._send(200, {
                        "auto_ingest_files": APP_CONFIG.get("auto_ingest_files", True),
                        "auto_save_chats": APP_CONFIG.get("auto_save_chats", True),
                        "auto_summarize_memories": APP_CONFIG.get("auto_summarize_memories", True),
                        "auto_search_before_answering": APP_CONFIG.get("auto_search_before_answering", True),
                        "auto_learn_corrections": APP_CONFIG.get("auto_learn_corrections", True),
                        "stats": assistant.db.stats(),
                    })
                elif path == "/session":
                    session_id = query.get("id", [""])[0]
                    if not session_id:
                        self._send(400, {"error": "Missing id query parameter"})
                        return
                    self._send(200, {"id": session_id, "messages": assistant.db.messages_for_session(session_id)})
                else:
                    self._send(404, {"error": "Use GET /health, /personas, /tools, /todos, /sessions, /session?id=..., POST /chat, /train, /todo, or /reset"})

            def do_POST(self):
                if self.path not in {"/chat", "/train", "/reset", "/todo", "/delete_session", "/persona", "/persona/import", "/persona/knowledge-pack", "/marketplace/install", "/knowledge/ingest", "/knowledge/scan", "/memory/summarize"}:
                    self._send(404, {"error": "Unknown endpoint"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    if self.path == "/persona/knowledge-pack":
                        result = attach_knowledge_pack(assistant.db, str(data.get("persona", "")), str(data.get("pack_id", "")))
                        self._send(200, {"ok": True, **result})
                        return

                    if self.path == "/marketplace/install":
                        item_id = str(data.get("id", ""))
                        source = str(data.get("source", "curated"))
                        if source == "curated":
                            item = MARKETPLACE_AGENTS.get(item_id)
                            if not item:
                                raise ValueError("Marketplace agent not found")
                            profile = dict(item["profile"])
                            key, spec = create_custom_persona(item["name"], item["vibe"], assistant.openai, profile)
                        else:
                            source_spec = CUSTOM_PERSONAS.get(item_id)
                            if not source_spec or source_spec.get("visibility") != "shared":
                                raise ValueError("Shared agent not found")
                            profile = _persona_export(item_id, source_spec)
                            key, spec = create_custom_persona(source_spec["name"], source_spec["short"], assistant.openai, profile)
                        for pack_id in spec.get("knowledge_packs", []):
                            attach_knowledge_pack(assistant.db, key, pack_id)
                        self._send(200, {"ok": True, "key": key, "persona": {**_persona_public(spec), "progress": assistant.db.agent_progress(key)}})
                        return

                    if self.path == "/knowledge/scan":
                        self._send(200, {"ok": True, **assistant.auto_ingest_files(force=True), "stats": assistant.db.stats()})
                        return

                    if self.path == "/memory/summarize":
                        summary = assistant.auto_summarize_memory()
                        self._send(200, {"ok": True, "summary": summary})
                        return

                    if self.path == "/knowledge/ingest":
                        provider = (data.get("provider") or "wikipedia").strip().lower()
                        topic = (data.get("topic") or "").strip()
                        limit = int(data.get("limit", 5))
                        if not topic:
                            raise ValueError("topic is required")
                        result = assistant.db.ingest_public_data(provider, topic, limit)
                        self._send(200, {"ok": True, **result, "stats": assistant.db.stats()})
                        return

                    if self.path == "/persona":
                        profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
                        key, spec = create_custom_persona(data.get("name", ""), data.get("vibe", ""), assistant.openai, profile)
                        for goal in spec.get("goals", []):
                            assistant.db.add_fact(key, f"Agent goal: {goal}")
                        if spec.get("starter_knowledge"):
                            assistant.db.store_knowledge_source(
                                f"agent:{key}:starter",
                                "agent_studio",
                                f"{spec['name']} starter knowledge",
                                f"antimony://agent/{key}",
                                spec["starter_knowledge"],
                                {"persona": key, "type": "starter_knowledge"},
                            )
                        for pack_id in spec.get("knowledge_packs", []):
                            attach_knowledge_pack(assistant.db, key, pack_id)
                        assistant.set_persona(key)
                        assistant.new_conversation()
                        self._send(200, {"ok": True, "key": key, "persona": {**_persona_public(spec), "progress": assistant.db.agent_progress(key)}})
                        return

                    if self.path == "/persona/import":
                        package = data.get("agent") if isinstance(data.get("agent"), dict) else data
                        if package.get("format") != "antimony-agent-v1":
                            raise ValueError("Unsupported agent package")
                        profile = {
                            "role": package.get("role"), "purpose": package.get("purpose"), "traits": package.get("traits", []),
                            "goals": package.get("goals", []), "voice_style": package.get("voice_style"),
                            "visibility": package.get("visibility"), "template": package.get("template"),
                            "appearance": package.get("appearance"), "greeting": package.get("greeting"),
                            "instructions": package.get("instructions"), "starter_knowledge": package.get("starter_knowledge"),
                            "knowledge_packs": package.get("knowledge_packs", []),
                        }
                        key, spec = create_custom_persona(package.get("name", "Imported Agent"), package.get("vibe", "custom"), assistant.openai, profile)
                        self._send(200, {"ok": True, "key": key, "persona": {**_persona_public(spec), "progress": assistant.db.agent_progress(key)}})
                        return

                    if self.path == "/delete_session":
                        session_id = data.get("id", "")
                        if not session_id:
                            raise ValueError("id is required")
                        removed = assistant.db.delete_session(session_id)
                        if assistant.session_id == session_id:
                            assistant.new_conversation()
                        self._send(200, {"ok": removed, "sessions": assistant.db.sessions(limit=100)})
                        return

                    if self.path == "/todo":
                        persona = data.get("persona", assistant.persona_key)
                        content = (data.get("content") or "").strip()
                        if not content:
                            raise ValueError("content is required")
                        assistant.db.add_todo(persona, content)
                        self._send(200, {"ok": True, "todos": assistant.db.todos(persona, limit=50)})
                        return

                    if self.path == "/reset":
                        persona = data.get("persona", assistant.persona_key)
                        assistant.set_persona(persona)
                        session_id = assistant.new_conversation()
                        self._send(200, {"ok": True, "session_id": session_id, "message": "New conversation started. Stored content was not deleted."})
                        return

                    if self.path == "/train":
                        persona = data.get("persona", assistant.persona_key)
                        assistant.set_persona(persona)
                        if data.get("question") and data.get("answer"):
                            assistant.db.add_qa_pair(persona, data["question"], data["answer"])
                            self._send(200, {"ok": True, "type": "qa_pair", "stats": assistant.db.stats()})
                            return
                        if data.get("intent") and data.get("text"):
                            assistant.db.add_training_example(data["intent"].lower(), data["text"])
                            assistant.retrain()
                            self._send(200, {"ok": True, "type": "intent", "stats": assistant.db.stats()})
                            return
                        raise ValueError("Use question+answer or intent+text")

                    message = data.get("message", "")
                    persona = data.get("persona", DEFAULT_PERSONA)
                    if not message:
                        raise ValueError("message is required")
                    reply = assistant.respond(message, persona)
                    self._send(200, {"persona": assistant.persona["name"], "reply": reply})
                except Exception as exc:
                    self._send(400, {"error": str(exc)})

            def do_DELETE(self):
                parsed = urlparse(self.path)
                if parsed.path not in {"/todo", "/session", "/persona"}:
                    self._send(404, {"error": "Unknown endpoint"})
                    return
                query = parse_qs(parsed.query)
                if parsed.path == "/persona":
                    key = query.get("key", [""])[0].strip()
                    if not key:
                        self._send(400, {"error": "Missing key query parameter"})
                        return
                    try:
                        removed = delete_custom_persona(key)
                    except ValueError as exc:
                        self._send(400, {"error": str(exc)})
                        return
                    if assistant.persona_key == key:
                        assistant.set_persona(DEFAULT_PERSONA)
                        assistant.new_conversation()
                    self._send(200, {"ok": True, "deleted": key, "name": removed["name"]})
                    return
                if parsed.path == "/session":
                    session_id = query.get("id", [""])[0]
                    if not session_id:
                        self._send(400, {"error": "Missing id query parameter"})
                        return
                    removed = assistant.db.delete_session(session_id)
                    if assistant.session_id == session_id:
                        assistant.new_conversation()
                    self._send(200, {"ok": removed, "sessions": assistant.db.sessions(limit=100)})
                    return

                persona = query.get("persona", [assistant.persona_key])[0]
                todo_id = query.get("id", [""])[0]
                if not todo_id.isdigit():
                    self._send(400, {"error": "Missing numeric id"})
                    return
                removed = assistant.db.delete_todo(persona, int(todo_id))
                self._send(200, {"ok": removed, "todos": assistant.db.todos(persona, limit=50)})

            def log_message(self, *_args):
                return

        selected_port = port
        for candidate in range(port, port + 10):
            try:
                self.server = ThreadingHTTPServer((host, candidate), Handler)
                selected_port = candidate
                break
            except OSError:
                continue
        if not self.server:
            raise RuntimeError(f"No free API port found from {port} to {port + 9}.")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://{host}:{selected_port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None


class AssistantApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Local Anime AI Assistant")
        self.root.geometry("1060x700")
        self.root.minsize(900, 580)
        self.assistant = AnimeAssistant()
        self.api = AssistantAPI(self.assistant)
        self.api_url = self.api.start()
        self.persona = tk.StringVar(value=DEFAULT_PERSONA)
        self.status = tk.StringVar(value=f"SQLite memory + API: {self.api_url}")
        self.model_choice = tk.StringVar(value=self.llm_mode())
        self.dark_mode = tk.BooleanVar(value=True)
        self.voice = VoiceEngine()
        self.last_reply = ""
        self.avatar_label = None
        self.name_label = None
        self.subtitle_label = None
        self.sessions_list = None
        self._session_rows = []
        self.avatar_images = {}
        self._build_ui()
        self._add_message(self.assistant.persona["name"], "Ready. I use SQLite memory, sessions, tools, voice, and a local API. New Chat never deletes saved/generated content.")
        self.refresh_sessions()

    def llm_mode(self):
        if self.assistant.openai.enabled:
            return f"OpenAI: {self.assistant.openai.model}"
        if self.assistant.llm.enabled:
            return f"Ollama: {self.assistant.llm.model}"
        return "Built-in fallback"

    def _load_avatar(self, key):
        path = PERSONAS[key]["image"]
        if not path.exists():
            path = ASSET_DIR / "anime_assistant.png"
        image = tk.PhotoImage(file=str(path))
        factor = max(1, image.width() // 260)
        return image.subsample(factor, factor)

    def _build_ui(self):
        self.root.configure(bg="#0f1115")
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        side = tk.Frame(self.root, bg="#151820", width=270)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)

        self.avatar_images[DEFAULT_PERSONA] = self._load_avatar(DEFAULT_PERSONA)
        self.avatar_label = tk.Label(side, image=self.avatar_images[DEFAULT_PERSONA], bg="#151820")
        self.avatar_label.pack(pady=(12, 6))

        self.name_label = tk.Label(side, text=self.assistant.persona["name"], fg="#fff4e8", bg="#151820", font=("Segoe UI", 20, "bold"))
        self.name_label.pack()

        tk.Label(side, text="Assistants", fg="#aeb8c2", bg="#151820", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(8, 2))
        for key, spec in PERSONAS.items():
            tk.Radiobutton(
                side, text=spec["name"], value=key, variable=self.persona,
                command=self.change_persona, indicatoron=False, bg="#202630", fg="#f6f1e8",
                selectcolor="#38424f", activebackground="#38424f", activeforeground="#ffffff",
                font=("Segoe UI", 9), relief="flat", padx=8, pady=3,
            ).pack(fill="x", padx=18, pady=2)

        tool_panel = tk.Frame(side, bg="#151820")
        tool_panel.pack(fill="x", padx=18, pady=(10, 0))
        for label, command in [
            ("New Chat", self.new_chat),
            ("Tools", self.show_tools),
            ("Memory", self.show_memory),
            ("Memory Viewer", self.open_memory_viewer),
            ("Export Chat", self.export_chat),
            ("Theme", self.toggle_theme),
            ("Speak", self.speak_last),
            ("Voice", self.voice_input),
        ]:
            tk.Button(
                tool_panel, text=label, command=command, bg="#252c36", fg="#f6f1e8",
                activebackground="#3a4653", activeforeground="#ffffff", relief="flat",
                font=("Segoe UI", 8), padx=6, pady=4,
            ).pack(fill="x", pady=2)

        tk.Label(side, text="Model", fg="#aeb8c2", bg="#151820", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(8, 2))
        tk.OptionMenu(side, self.model_choice, self.llm_mode(), "Built-in fallback", "Ollama", "OpenAI").pack(fill="x", padx=18)

        tk.Label(side, text="Saved Chats", fg="#aeb8c2", bg="#151820", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(10, 0))
        self.sessions_list = tk.Listbox(
            side, bg="#0e1319", fg="#f6f1e8", selectbackground="#3f5963",
            relief="flat", height=7, font=("Segoe UI", 8), activestyle="none",
        )
        self.sessions_list.pack(fill="x", padx=18, pady=(4, 4))
        session_buttons = tk.Frame(side, bg="#151820")
        session_buttons.pack(fill="x", padx=18)
        tk.Button(
            session_buttons, text="Load", command=self.load_selected_session, bg="#252c36", fg="#f6f1e8",
            activebackground="#334150", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Button(
            session_buttons, text="Refresh", command=self.refresh_sessions, bg="#252c36", fg="#f6f1e8",
            activebackground="#334150", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, padx=(3, 0))

        tk.Label(
            side,
            text=f"LLM: {self.llm_mode()}",
            fg="#7fd8d2",
            bg="#151820",
            wraplength=220,
            justify="center",
            font=("Segoe UI", 9),
        ).pack(side="bottom", pady=14)

        main = tk.Frame(self.root, bg="#0f1115")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.chat = scrolledtext.ScrolledText(
            main, bg="#0a0d12", fg="#f6f1e8", insertbackground="#ffffff",
            font=("Segoe UI", 11), wrap="word", relief="flat", padx=22, pady=20,
        )
        self.chat.grid(row=0, column=0, sticky="nsew", padx=18, pady=(18, 10))
        self.chat.configure(state="disabled")

        bottom = tk.Frame(main, bg="#0f1115")
        bottom.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)

        self.entry = tk.Entry(bottom, bg="#171d25", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Segoe UI", 12))
        self.entry.grid(row=0, column=0, sticky="ew", ipady=12, padx=(0, 10))
        self.entry.bind("<Return>", lambda _event: self.send())

        tk.Button(
            bottom, text="Send", command=self.send, bg="#d76d5f", fg="#ffffff",
            activebackground="#e28678", activeforeground="#ffffff", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=22, pady=10,
        ).grid(row=0, column=1)

        tk.Label(main, textvariable=self.status, fg="#8fb7b3", bg="#0f1115", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))

    def change_persona(self, announce=True):
        key = self.persona.get()
        self.assistant.set_persona(key)
        if key not in self.avatar_images:
            self.avatar_images[key] = self._load_avatar(key)
        self.avatar_label.configure(image=self.avatar_images[key])
        self.name_label.configure(text=self.assistant.persona["name"])
        if announce:
            self._add_message(self.assistant.persona["name"], self.assistant.persona["hello"])
        self.refresh_sessions()

    def new_chat(self):
        self.assistant.new_conversation()
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._add_message(self.assistant.persona["name"], "New conversation started. Old generated content is still saved in SQLite.")
        self.status.set(f"New session: {self.assistant.session_id}")
        self.refresh_sessions()

    def refresh_sessions(self):
        if not self.sessions_list:
            return
        self.sessions_list.delete(0, "end")
        self._session_rows = self.assistant.db.sessions(limit=50)
        for session in self._session_rows:
            timestamp = datetime.fromtimestamp(session["created_at"]).strftime("%m/%d %H:%M")
            name = PERSONAS.get(session["persona"], PERSONAS[DEFAULT_PERSONA])["name"]
            self.sessions_list.insert("end", f"{timestamp} {name}: {session['title']}")

    def load_selected_session(self):
        if not self.sessions_list:
            return
        selection = self.sessions_list.curselection()
        if not selection:
            return
        session = self._session_rows[selection[0]]
        self.assistant.set_persona(session["persona"])
        self.persona.set(session["persona"])
        self.assistant.session_id = session["id"]
        self.change_persona(announce=False)
        messages = self.assistant.db.messages_for_session(session["id"])
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        for message in messages:
            sender = "You" if message["role"] == "user" else PERSONAS.get(message["persona"], PERSONAS[DEFAULT_PERSONA])["name"]
            self._add_message(sender, message["content"])
        self.status.set(f"Loaded session: {session['title']}")

    def show_tools(self):
        self._submit_text("tools")

    def show_memory(self):
        self._submit_text("list memory")

    def open_memory_viewer(self):
        viewer = tk.Toplevel(self.root)
        viewer.title("Antimony Memory")
        viewer.geometry("560x460")
        text = scrolledtext.ScrolledText(viewer, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        memory = self.assistant.memory
        text.insert("end", "Short-term memory\n")
        for message in memory.short_term_memory:
            text.insert("end", f"- {message['role']}: {message['content']}\n")
        text.insert("end", "\nLong-term memory\n")
        for fact in memory.long_term_memory:
            text.insert("end", f"- {fact}\n")
        text.insert("end", "\nSkill memory\n")
        for pair in memory.skill_memory:
            text.insert("end", f"- Q: {pair['question']}\n  A: {pair['answer']}\n")
        text.configure(state="disabled")

    def export_chat(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        messages = self.assistant.db.messages_for_session(self.assistant.session_id)
        lines = []
        for message in messages:
            sender = "You" if message["role"] == "user" else PERSONAS.get(message["persona"], PERSONAS[DEFAULT_PERSONA])["name"]
            lines.append(f"{sender}: {message['content']}")
        Path(path).write_text("\n\n".join(lines), encoding="utf-8")
        self.status.set(f"Exported chat: {path}")

    def toggle_theme(self):
        self.dark_mode.set(not self.dark_mode.get())
        bg = "#0f1115" if self.dark_mode.get() else "#f4f6fb"
        fg = "#f6f1e8" if self.dark_mode.get() else "#17202a"
        self.root.configure(bg=bg)
        if self.chat:
            self.chat.configure(bg=bg, fg=fg, insertbackground=fg)

    def speak_last(self):
        text = self.last_reply or "No assistant reply to speak yet."
        self.status.set("Speaking...")
        persona = dict(self.assistant.persona)
        threading.Thread(target=lambda: self.voice.speak(text, persona), daemon=True).start()
        self.status.set(f"SQLite memory + API: {self.api_url}")

    def voice_input(self):
        self.status.set("Listening...")

        def worker():
            text, err = self.voice.listen()
            if err:
                self.root.after(0, lambda: self._add_message("Voice", err))
                self.root.after(0, lambda: self.status.set(f"SQLite memory + API: {self.api_url}"))
                return
            self.root.after(0, lambda: self._submit_text(text, speak_reply=True))

        threading.Thread(target=worker, daemon=True).start()

    def _add_message(self, sender, text):
        self.chat.configure(state="normal")
        tag = "user_sender" if sender == "You" else "assistant_sender"
        body_tag = "user_body" if sender == "You" else "assistant_body"
        self.chat.insert("end", f"{sender}\n", (tag,))
        for part, is_url in self._split_links(text):
            if is_url:
                link_tag = f"link_{len(self.chat.tag_names())}_{int(time.time() * 1000)}"
                self.chat.insert("end", part, (body_tag, "hyperlink", link_tag))
                self.chat.tag_bind(link_tag, "<Button-1>", lambda _event, url=part: webbrowser.open(url))
            else:
                self.chat.insert("end", part, (body_tag,))
        self.chat.insert("end", "\n\n", (body_tag,))
        self.chat.tag_config("assistant_sender", foreground="#7fd8d2", font=("Segoe UI", 11, "bold"), spacing1=8)
        self.chat.tag_config("user_sender", foreground="#f08a7f", font=("Segoe UI", 11, "bold"), spacing1=8)
        self.chat.tag_config("assistant_body", foreground="#f6f1e8", spacing3=10)
        self.chat.tag_config("user_body", foreground="#e9edf0", lmargin1=16, lmargin2=16, spacing3=10)
        self.chat.tag_config("hyperlink", foreground="#6bbcff", underline=True)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _split_links(self, text):
        pieces = []
        last = 0
        for match in URL_RE.finditer(text):
            if match.start() > last:
                pieces.append((text[last:match.start()], False))
            pieces.append((match.group(0), True))
            last = match.end()
        if last < len(text):
            pieces.append((text[last:], False))
        return pieces

    def send(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._submit_text(text)

    def _submit_text(self, text, speak_reply=False):
        self._add_message("You", text)
        self.status.set("Thinking...")
        threading.Thread(target=self._answer, args=(text, speak_reply), daemon=True).start()

    def _answer(self, text, speak_reply=False):
        persona_key = self.persona.get()
        reply = self.assistant.respond(text, persona_key)
        self.root.after(0, lambda: self._finish(reply, speak_reply))

    def _finish(self, reply, speak_reply=False):
        self.last_reply = reply
        self._add_message(self.assistant.persona["name"], reply)
        self.status.set(f"SQLite memory + API: {self.api_url}")
        self.refresh_sessions()
        if speak_reply:
            persona = dict(self.assistant.persona)
            self.status.set("Speaking answer...")
            threading.Thread(target=lambda: self.voice.speak(reply, persona), daemon=True).start()


def run_cli(once=None, persona=DEFAULT_PERSONA):
    assistant = AnimeAssistant(persona)
    if once:
        reply = assistant.respond(once, persona)
        try:
            print(reply)
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or "utf-8"
            sys.stdout.buffer.write((reply + "\n").encode(encoding, errors="replace"))
        return
    print("Local Anime AI Assistant")
    print("Personas: " + ", ".join(f"{key}={spec['name']}" for key, spec in PERSONAS.items()))
    print("Type /exit to quit. Type /persona soren|renji|kael|mira to switch.")
    print("Train with: teach: question => answer")
    print("Train intent with: train intent code: how do I make a Python function")
    while True:
        user_text = input("\nYou: ").strip()
        if user_text.lower() in {"/exit", "exit", "quit"}:
            break
        if user_text.startswith("/persona "):
            persona = user_text.split(maxsplit=1)[1].strip().lower()
            assistant.set_persona(persona)
            print(f"Persona set to {assistant.persona['name']}.")
            continue
        print(f"\n{assistant.persona['name']}: {assistant.respond(user_text, persona)}")


def run_api():
    assistant = AnimeAssistant()
    api = AssistantAPI(assistant)
    url = api.start()
    print(f"API running at {url}")
    print("GET /health, GET /personas, POST /chat")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping API.")


def main():
    parser = argparse.ArgumentParser(description="Local anime AI assistant with SQLite memory and API.")
    parser.add_argument("--cli", action="store_true", help="Run in the terminal.")
    parser.add_argument("--api", action="store_true", help="Run only the local API server.")
    parser.add_argument("--once", help="Send one message and print the response.")
    parser.add_argument("--persona", default=DEFAULT_PERSONA, choices=list(PERSONAS.keys()))
    parser.add_argument("--teach-question", help="Question to teach the selected persona.")
    parser.add_argument("--teach-answer", help="Answer for --teach-question.")
    parser.add_argument("--train-intent", help="Intent label to train.")
    parser.add_argument("--train-text", help="Example text for --train-intent.")
    args = parser.parse_args()

    if args.teach_question and args.teach_answer:
        assistant = AnimeAssistant(args.persona)
        assistant.db.add_qa_pair(args.persona, args.teach_question, args.teach_answer)
        print(f"Trained {assistant.persona['name']} with one Q&A pair.")
        return
    if args.train_intent and args.train_text:
        assistant = AnimeAssistant(args.persona)
        assistant.db.add_training_example(args.train_intent.lower(), args.train_text)
        assistant.retrain()
        print(f"Added training example for intent '{args.train_intent.lower()}'.")
        return

    if args.api:
        run_api()
        return
    if args.cli or args.once:
        run_cli(args.once, args.persona)
        return

    root = tk.Tk()
    AssistantApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
