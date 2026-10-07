# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: **Security → Report a vulnerability** on this repository
(private vulnerability reporting). Include the affected version or commit, reproduction steps
and the impact you see.

You can expect an acknowledgement within a few days. Fixes are released as soon as practical,
and reporters are credited unless they prefer otherwise.

## Scope

This repository contains the CrowSpeak engine, gateway and reference CLI. API keys and
credentials must never be committed; use `.env` (git-ignored) and see `.env.example`.
