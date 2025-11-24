import json
import os
import subprocess
import sys
from pathlib import Path


def get_diff() -> str:
    """
    Get the diff for the current PR or local changes.
    - In CI: use BASE_BRANCH (e.g. origin/develop) vs HEAD.
    - Locally: just use `git diff` against the working tree.
    """
    base_branch = os.getenv("BASE_BRANCH")

    try:
        if base_branch:
            # CI mode: compare base branch with HEAD
            diff_cmd = ["git", "diff", base_branch, "HEAD"]
        else:
            # Local mode: show unstaged/staged changes
            diff_cmd = ["git", "diff"]

        diff = subprocess.check_output(diff_cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("[WARN] Error while getting diff:")
        print(e.output)
        return "No diff could be obtained. This may be a fresh repo with no git history yet."

    diff = diff.strip()
    if not diff:
        return "No relevant changes detected in the diff."
    return diff


def load_file(path: Path) -> str:
    """Load a text file, return empty string if not found."""
    if not path.exists():
        print(f"[WARN] File not found: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def build_prompt(product_spec: str, ai_checks: str, diff: str) -> str:
    """
    Build the prompt that will be sent to the LLM.
    This combines project specification, AI checks instructions and the code diff.
    """
    parts = []

    parts.append("You are an automated code reviewer integrated into a CI pipeline.")
    parts.append(
        "You must strictly follow the instructions and output format defined in the AI checks document."
    )

    if product_spec:
        parts.append("\n--- PROJECT SPECIFICATION ---\n")
        parts.append(product_spec)

    if ai_checks:
        parts.append("\n--- AI CHECKS DOCUMENT ---\n")
        parts.append(ai_checks)

    parts.append("\n--- DIFF TO REVIEW ---\n")
    parts.append("The following is the unified diff of the code changes:")
    parts.append("\n```diff\n")
    parts.append(diff)
    parts.append("\n```\n")

    full_prompt = "\n".join(parts)
    return full_prompt


def call_llm(prompt: str) -> str:
    """
    Placeholder for the LLM call.

    For now, this runs in 'dry-run' mode:
    - If no OPENAI_API_KEY is set, it returns a dummy JSON.
    - When the key and client are available, this function can be updated
      to actually call the model.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("[INFO] No OPENAI_API_KEY found. Running in dry-run mode.")
        # Dummy response: everything passes
        dummy_result = {
            "overall_status": "pass",
            "checks": [
                {
                    "name": "readability",
                    "status": "pass",
                    "details": "Dry-run: no real evaluation performed.",
                },
                {
                    "name": "security_basic",
                    "status": "pass",
                    "details": "Dry-run: no real evaluation performed.",
                },
                {
                    "name": "consistency_with_project",
                    "status": "pass",
                    "details": "Dry-run: no real evaluation performed.",
                },
                {
                    "name": "tests",
                    "status": "pass",
                    "details": "Dry-run: no real evaluation performed.",
                },
            ],
            "notes": ["Dry-run mode: LLM was not called."],
        }
        return json.dumps(dummy_result)

    # When you get the key and choose a client (OpenAI, etc.), you can implement:
    #
    # from openai import OpenAI
    # client = OpenAI(api_key=api_key)
    #
    # response = client.chat.completions.create(
    #     model="gpt-4.1-mini",
    #     messages=[
    #         {"role": "system", "content": "You are a strict automated code reviewer."},
    #         {"role": "user", "content": prompt},
    #     ],
    #     temperature=0,
    # )
    # content = response.choices[0].message.content
    #
    # return content
    #
    # For now, even if the key exists, we still return a dummy payload:

    print("[INFO] OPENAI_API_KEY is set, but LLM call is not implemented yet. Returning dummy result.")
    dummy_result = {
        "overall_status": "pass",
        "checks": [
            {
                "name": "readability",
                "status": "pass",
                "details": "Placeholder result. Implement LLM call to get real evaluation.",
            },
            {
                "name": "security_basic",
                "status": "pass",
                "details": "Placeholder result. Implement LLM call to get real evaluation.",
            },
            {
                "name": "consistency_with_project",
                "status": "pass",
                "details": "Placeholder result. Implement LLM call to get real evaluation.",
            },
            {
                "name": "tests",
                "status": "pass",
                "details": "Placeholder result. Implement LLM call to get real evaluation.",
            },
        ],
        "notes": ["LLM call not implemented yet; this is a placeholder response."],
    }
    return json.dumps(dummy_result)


def main() -> None:
    # 1. Load documentation
    product_spec_path = Path("docs/product_spec.md")
    ai_checks_path = Path("ci/ai_checks.md")

    product_spec = load_file(product_spec_path)
    ai_checks = load_file(ai_checks_path)

    # 2. Get diff
    diff = get_diff()

    print("=== Diff preview (first 2000 characters) ===")
    print(diff[:2000])
    print("\n=== End of diff preview ===\n")

    # 3. Build prompt
    prompt = build_prompt(product_spec, ai_checks, diff)

    # (Optional) Debug: see part of the prompt
    print("=== Prompt preview (first 3000 characters) ===")
    print(prompt[:3000])
    print("\n=== End of prompt preview ===\n")

    # 4. Call LLM (currently dry-run)
    raw_output = call_llm(prompt)

    print("=== Raw model output ===")
    print(raw_output)
    print("=== End of model output ===\n")

    # 5. Try to parse JSON
    try:
        result = json.loads(raw_output)
    except json.JSONDecodeError:
        print("[ERROR] Model output is not valid JSON. Failing the check.")
        sys.exit(1)

    overall_status = result.get("overall_status", "fail")
    checks = result.get("checks", [])
    notes = result.get("notes", [])

    print("=== Parsed result ===")
    print(json.dumps(result, indent=2))
    print("=== End of parsed result ===\n")

    # 6. Decide CI status
    if overall_status != "pass":
        print("❌ AI review failed according to overall_status.")
        print("Failed checks:")
        for c in checks:
            if c.get("status") == "fail":
                print(f"- {c.get('name')}: {c.get('details')}")
        if notes:
            print("\nNotes:")
            for n in notes:
                print(f"- {n}")
        sys.exit(1)

    print("✅ AI review passed (dummy mode).")
    if notes:
        print("Notes:")
        for n in notes:
            print(f"- {n}")
    sys.exit(0)


if __name__ == "__main__":
    main()
