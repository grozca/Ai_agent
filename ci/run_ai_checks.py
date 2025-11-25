#!/usr/bin/env python
"""
AI code reviewer integrado con Ollama.

- Obtiene el diff de git del último commit (con fallback si no hay HEAD~1).
- Carga:
    - ci/ai_checks.md  (reglas y esquema JSON)
    - product_spec.md  (contexto del proyecto, si existe)
- Intenta llamar a Ollama (modelo definido en .env).
- Siempre imprime un JSON válido:
    - Si la llamada a la IA funciona: usa la respuesta de la IA.
    - Si falla o hay timeout: devuelve un JSON "fallback" marcando el error.

Requisitos:
    pip install requests python-dotenv
    Ollama corriendo y modelo instalado (ej: llama3:8b):
        ollama run llama3:8b "Hola"
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Tuple

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Cargar variables de entorno (.env en la raíz del repo)
# ---------------------------------------------------------------------------

load_dotenv()

# Configuración principal
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MAX_DIFF_CHARS = int(os.getenv("AI_REVIEW_MAX_DIFF_CHARS", "2000"))
REQUEST_TIMEOUT = int(os.getenv("AI_REVIEW_TIMEOUT_SECONDS", "300"))

# Si AI_REVIEW_STRICT=1, un fallo de la IA hace fallar el CI.
STRICT_MODE = os.getenv("AI_REVIEW_STRICT", "0") == "1"


# ---------------------------------------------------------------------------
# Utilidades shell/Git
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str], cwd: str | None = None) -> Tuple[int, str, str]:
    """Ejecuta un comando y devuelve (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def get_git_diff() -> str:
    """
    Obtiene un diff útil para revisar.

    Prioridad:
    1. Diff entre HEAD~1 y HEAD (último commit).
    2. Diff de cambios sin commitear.
    3. Mensaje de error explicando qué pasó.
    """
    # 1) Intentar diff entre HEAD~1 y HEAD
    rc, _, _ = run_cmd(["git", "rev-parse", "HEAD~1"])
    if rc == 0:
        rc, out, err = run_cmd(["git", "diff", "--unified=0", "HEAD~1"])
        if rc == 0 and out.strip():
            return out

    # 2) Fallback: diff de cambios actuales sin commitear
    rc, out, err = run_cmd(["git", "diff", "--unified=0"])
    if rc == 0 and out.strip():
        header = "# Fallback diff (no se pudo usar HEAD~1)\n"
        return header + out

    # 3) Nada útil: devolver explicación + git status
    status_rc, status_out, status_err = run_cmd(
        ["git", "status", "--short", "--branch"]
    )
    msg = textwrap.dedent(
        f"""
        No se pudo obtener un diff útil para revisar.

        Último error de git:
        {err or status_err}

        Salida de 'git status --short --branch':
        {status_out}
        """
    ).strip()
    return msg


# ---------------------------------------------------------------------------
# Carga de documentos (reglas y spec)
# ---------------------------------------------------------------------------

def load_ai_checks_document() -> str:
    """
    Carga el documento de reglas de revisión (AI checks document).

    Prioridad:
    - ci/ai_checks.md
    - .github/ai-checks.md
    """
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "ai_checks.md",
        script_dir.parent / ".github" / "ai-checks.md",
    ]

    for path in candidates:
        if path.exists():
            print(f"[DEBUG] Usando AI checks de: {path}")
            return path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        "No se encontró ci/ai_checks.md ni .github/ai-checks.md. "
        "Se necesita uno de estos para saber las reglas y el formato JSON."
    )


def load_product_spec() -> str:
    """
    Carga product_spec.md si existe, para dar contexto del proyecto.

    Busca en:
    - product_spec.md en la raíz
    - docs/product_spec.md
    """
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    candidates = [
        repo_root / "product_spec.md",
        repo_root / "docs" / "product_spec.md",
    ]

    for path in candidates:
        if path.exists():
            print(f"[DEBUG] Usando product spec de: {path}")
            return path.read_text(encoding="utf-8")

    print("[DEBUG] No se encontró product_spec.md, se continúa sin contexto extra.")
    return ""


# ---------------------------------------------------------------------------
# Cliente de Ollama
# ---------------------------------------------------------------------------

def call_ollama(
    prompt: str,
    model: str = DEFAULT_OLLAMA_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
    temperature: float = 0.1,
) -> str:
    """
    Llama a Ollama usando /api/generate (sin streaming) y devuelve el campo 'response'.
    """
    api_url = url.rstrip("/") + "/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    print(f"[DEBUG] Llamando a Ollama en {api_url} con modelo '{model}'...")
    print(f"[DEBUG] Timeout configurado: {REQUEST_TIMEOUT} segundos")
    resp = requests.post(api_url, json=payload, timeout=REQUEST_TIMEOUT)
    print("[DEBUG] Respuesta recibida de Ollama.")
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", "").strip()


# ---------------------------------------------------------------------------
# Construcción del prompt
# ---------------------------------------------------------------------------

def build_review_prompt(ai_checks_doc: str, product_spec: str, diff: str) -> str:
    """
    Construye el prompt principal para el modelo.
    """
    trimmed_diff = diff
    if len(trimmed_diff) > MAX_DIFF_CHARS:
        trimmed_diff = trimmed_diff[:MAX_DIFF_CHARS]
        trimmed_diff += (
            f"\n\n[Diff truncado a {MAX_DIFF_CHARS} caracteres para ajustarse al contexto.]"
        )

    prompt = f"""
    You are an automated code reviewer integrated into a CI pipeline.

    You MUST strictly follow the instructions and JSON output format defined
    in the AI checks document.

    --- PROJECT SPECIFICATION (CONTEXT) ---
    {product_spec}
    --- END PROJECT SPECIFICATION ---

    --- AI CHECKS DOCUMENT (RULES + REQUIRED JSON SCHEMA) ---
    {ai_checks_doc}
    --- END AI CHECKS DOCUMENT ---

    --- DIFF TO REVIEW ---
    {trimmed_diff}
    --- END DIFF ---

    VERY IMPORTANT INSTRUCTIONS:

    - Your output MUST be VALID RAW JSON, with NO markdown formatting.
    - DO NOT wrap your response in triple backticks (```json or ```).
    - DO NOT add explanations before or after the JSON.
    - DO NOT include comments in the JSON.
    - The JSON MUST be directly parseable by Python's json.loads().
    - The JSON MUST follow the exact schema described in the AI checks document
      (including overall_status, checks, notes, etc.).
    - Base your evaluation ONLY on:
        - The diff provided
        - The AI checks document
        - The project specification
    - Answer explanations in Spanish where appropriate, but keep code identifiers,
      function names and technical terms in English.
    """

    return textwrap.dedent(prompt).strip()


# ---------------------------------------------------------------------------
# Limpieza y parseo del JSON
# ---------------------------------------------------------------------------

def clean_and_parse_json(response: str) -> dict:
    """
    Limpia la respuesta del modelo (quitando ```json ... ``` si existe)
    y devuelve un dict JSON parseado.
    """
    raw = response.strip()

    # 1) Si viene envuelto en ```...``` lo limpiamos
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1].strip()
        else:
            raw = raw.replace("```", "").strip()

    # 2) Extraer solo lo que hay entre { ... }
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{") : raw.rfind("}") + 1]

    # 3) Intentar parsear el JSON
    parsed = json.loads(raw)  # si falla, que lance la excepción
    return parsed


# ---------------------------------------------------------------------------
# Fallback JSON (cuando la IA falla)
# ---------------------------------------------------------------------------

def build_fallback_result(error_message: str) -> dict:
    """
    Construye un JSON mínimo válido cuando no se puede llamar a la IA.
    """
    return {
        "overall_status": "unknown",
        "checks": [],
        "notes": [
            "AI reviewer no pudo ejecutarse correctamente.",
            f"Detalle técnico: {error_message}",
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("[DEBUG] Modelo cargado de .env:", os.getenv("OLLAMA_MODEL"))
    print("[DEBUG] URL de Ollama:", os.getenv("OLLAMA_URL"))

    print("=== AI Reviewer (Ollama) ===")
    print(f"Modelo: {DEFAULT_OLLAMA_MODEL}")
    print(f"Endpoint: {DEFAULT_OLLAMA_URL}")

    try:
        ai_checks_doc = load_ai_checks_document()
    except FileNotFoundError as e:
        print("❌", e)
        fallback = build_fallback_result(str(e))
        print("=== AI REVIEW JSON START ===")
        print(json.dumps(fallback, indent=2, ensure_ascii=False))
        print("=== AI REVIEW JSON END ===")
        return 1 if STRICT_MODE else 0

    product_spec = load_product_spec()
    diff = get_git_diff()

    if not diff.strip():
        print("No se encontraron cambios para revisar (diff vacío).")
        no_changes = {
            "overall_status": "pass",
            "checks": [],
            "notes": ["No se encontraron cambios para revisar."],
        }
        print("=== AI REVIEW JSON START ===")
        print(json.dumps(no_changes, indent=2, ensure_ascii=False))
        print("=== AI REVIEW JSON END ===")
        return 0

    print(
        f"[DEBUG] Longitud del diff: {len(diff)} caracteres "
        f"(se recorta a {MAX_DIFF_CHARS})"
    )

    prompt = build_review_prompt(ai_checks_doc, product_spec, diff)

    # Intentar llamada a la IA
    try:
        response = call_ollama(prompt)
        parsed = clean_and_parse_json(response)
    except (requests.Timeout, requests.RequestException, json.JSONDecodeError) as exc:
        print(f"❌ Error al llamar a la IA o parsear JSON: {exc}")
        parsed = build_fallback_result(str(exc))
        exit_code = 1 if STRICT_MODE else 0
    else:
        overall_status = parsed.get("overall_status")
        if overall_status == "fail":
            print("❌ overall_status = fail → marcando revisión como FALLIDA (exit 1).")
            exit_code = 1
        else:
            print("✅ overall_status != fail → revisión OK (exit 0).")
            exit_code = 0

    print("=== AI REVIEW JSON START ===")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    print("=== AI REVIEW JSON END ===")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
