# ShipCast Studio — 4-Track Hackathon Submission Kit

- **Live Public GitHub Repository:** https://github.com/Blackwrld04/shipcast-studio
- **Staged DEV.to Blog Draft (`edit_url`):** https://dev.to/olajide_abdulquadri_807ef/shipcast-studio-on-switch-rooms-cryptographically-verified-multi-agent-release-notes-3ilf-temp-slug-4446916/edit
- **Local Studio Workbench UI:** http://127.0.0.1:8765

This file contains everything needed to submit **ShipCast Studio** across **four prize tracks simultaneously**:
1. **Main Track 02: Best Personal or Creative Workflow (\$2,000)**
2. **Side Track: Code with Wispr (\$500)**
3. **Side Track: Best Blog (AirPods 5)**
4. **Social Track: `#HowISwitch` (5× Logitech Mechanical Keyboards)**

---

## 1. Two-Minute Demo Video Script (20% Presentation Score)

Keep two windows side-by-side on screen:
- **Left Half:** **Switch Console** (showing the Templates page + `#shipcast-studio-desk` and `#shipcast-verification-lab` rooms).
- **Right Half:** **ShipCast Studio Workbench** (`http://127.0.0.1:8765`).

### Scene-by-Scene Script (1m 45s total):

* **0:00 – 0:20 (The Problem & Why Switch Is Essential):**
  > *"Every developer loves shipping code, but hates the two-hour chore afterward: checking `git log`, re-running tutorial CLI commands by hand so code blocks don't lie, updating `CHANGELOG.md`, and drafting launch posts. A single chatbot in a channel fails here because it hallucinates CLI flags and spams the room. So we built **ShipCast Studio** on **Switch Rooms**."*

* **0:20 – 0:50 (1-Click Switch Template & Room Topology):**
  > *"In Switch Console, we import [`shipcast.template.yaml`](shipcast.template.yaml). In one pass, Switch creates three agents—`producer`, `verifier`, and `publisher`—and two linked rooms: `#shipcast-studio-desk` and `#shipcast-verification-lab`. Notice that `producer` has `addressing: anyone` and claims the exclusive `release-captain` role so two releases never collide, while `verifier` and `publisher` use `addressing: owner-agents` so only `producer` can trigger them."*

* **0:50 – 1:25 (Live Execution, Sandbox Receipts & 7-Rule Contract):**
  > *"In `#shipcast-studio-desk`, I trigger a release for `v0.2.0` (dictated with Wispr Flow). `producer` analyzes the git commit range, filters out noise commits, and follows the Switch room link into `#shipcast-verification-lab`. There, `verifier` runs every extracted CLI command and test in an isolated subprocess sandbox, signing a cryptographic `SHA-256` receipt (`21fe43f069b40485`). Then `publisher` validates the generated DEV.to tutorial and changelog against our room-scoped document `shipcast-editorial-contract`—passing all 7 rules, including Slack/Telegram-safe formatting."*

* **1:25 – 1:45 (Human-in-the-Loop Gate & Live Publish):**
  > *"Nothing ships on autopilot. Back in `#shipcast-studio-desk`, `producer` posts the verified receipt card and waits. When I reply `Approve publish`, it updates `CHANGELOG.md`, writes the signed `publication-receipt.json`, stages our DEV.to tutorial draft, and releases the `release-captain` role."*

---

## 2. Ready-to-Post `#HowISwitch` Social Posts (5× Logitech Keyboards)

Post on **X (Twitter)** and **LinkedIn** with a screenshot or clip of your Switch Console + Studio Workbench (`http://127.0.0.1:8765`):

### X / Twitter Post:
```text
Turned our post-release grind into a 2-room multi-agent pipeline with @SwitchAgents & @WeMakeDevs!

Built ShipCast Studio:
• Room 1 (#studio-desk): @producer claims an exclusive release-captain role & scores git commits 1–10
• Room 2 (#verification-lab): @verifier runs every tutorial CLI snippet in a sandbox & signs a SHA-256 receipt before @publisher drafts the DEV post & CHANGELOG
• Human replies "Approve publish" in chat to ship

1-click reproducible via shipcast.template.yaml! #HowISwitch
```

### LinkedIn Post:
```text
Writing code takes two hours; verifying tutorial snippets, updating CHANGELOG.md, and writing release notes takes another hour.

For the Flip the Switch Hackathon (@WeMakeDevs & @DevToolsAcademy), I built ShipCast Studio on Switch Rooms—an autonomous code-to-content and verified release studio.

Why Switch Rooms made this work:
1. Two Linked Rooms (`#studio-desk` ↔ `#verification-lab`): Keeps noisy subprocess sandbox logs backstage while the human control desk stays clean.
2. Addressing Boundaries & Exclusive Roles: `@producer` (`addressing: anyone`) holds the exclusive `release-captain` lock, while `@verifier` and `@publisher` (`addressing: owner-agents`) only accept structured handoffs.
3. Cryptographic Sandbox Verification: Every CLI command in the generated tutorial is executed in a real subprocess (`SHA-256` receipt signed) and checked against a 7-rule room contract before asking for human sign-off in chat.

#HowISwitch #AIAgents #OpenSource #DevTools
```

---

## 3. Best Blog Submission Draft (AirPods 5 Track)

The complete, contract-validated blog post is generated and ready at:
- [`dist/latest/devto-article.md`](dist/latest/devto-article.md)

---

## 4. Code with Wispr Checklist (\$500 Track)

1. Open the **Wispr Flow** desktop app and dictate your release prompt in `#shipcast-studio-desk`:
   > *"At producer, ship release version zero point two point zero from HEAD tilde three to HEAD and highlight how our two linked Switch rooms separate sandbox command verification from the human approval desk."*
2. Open **Insights** in the Wispr Flow desktop app and take a screenshot of your **Wispr usage scorecard**.
3. Attach that screenshot when submitting your project on the hackathon portal!

