# Project Specification

This repository aims to integrate an AI-powered automated code reviewer into the development workflow.

## Purpose

The AI reviewer must:

- Evaluate Pull Requests based on documented project rules.
- Ensure code quality before human reviewers step in.
- Provide structured feedback in a predictable JSON format.
- Act as a first-line filter for readability, security, consistency, and testing coverage.

## PR Expectations

Every Pull Request should:

1. Contain clear, maintainable, and well-structured code.
2. Not introduce security risks.
3. Follow the established coding conventions and directory structure.
4. Include or update tests when new logic is added.
5. Avoid unnecessary complexity or large unreviewed changes.

## Scope for the AI Reviewer

The AI reviewer analyzes:

- The diff provided by CI.
- The rules defined in `ci/ai_checks.md`.

It does **not** make architectural decisions or modify code — it only evaluates against the existing rules and provides feedback.

## Notes

This specification will grow as the project evolves.  
For now, it provides minimal context for the AI to anchor its evaluations.
