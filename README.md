# AI Reviewer for Code Changes (Ollama-Powered)

This project provides a **local AI-powered code review system** that analyzes Git diffs, applies project-specific rules, and produces a structured JSON report suitable for CI pipelines.  
It works entirely locally using **Ollama**, requiring no external APIs.

---

## 🚀 Features

- **Local AI Model** (llama3:8b or similar through Ollama)
- **Reads Git diffs** (HEAD~1 or fallback to unstaged changes)
- **Loads custom review rules** from `ci/ai_checks.md`
- **Optional project context** from `product_spec.md`
- **Produces strictly valid JSON output**
- **Automatic code quality checks**:
  - Readability  
  - Security basics  
  - Consistency with project  
  - Tests coverage  
- **CI-friendly exit codes**
  - `0` = success  
  - `1` = failed review  
- **Fallback mode** when AI timeout/errors occur
- **Fully configurable via `.env`**

---

## 📂 Project Structure

