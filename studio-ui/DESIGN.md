# ShipCast Studio — Design System

ShipCast Studio is a local release desk: one workspace for reading the release, checking the evidence, reviewing the Switch Rooms handoff, reading the generated content, and downloading the bundle. The interface is intentionally quiet around the work — warm paper surfaces, one dark pipeline panel, and receipts shown as facts rather than decoration.

## Principles

1. **One home for each question.** The top navigation is the only navigation. A view never duplicates a card, stat, or tab that already lives elsewhere.
2. **Evidence over chrome.** Verification counts, contract rules, commit scores, receipt hashes, and publication state are derived from the loaded bundle. No hardcoded readiness percentages or decorative players.
3. **Show the next action, not every action.** Run, publish, and copy are available where they are relevant. Destructive changes sit behind a modal with a summary.
4. **Readable at a glance, complete on inspection.** Headlines and counts answer the first question; tables, expandable command output, and the full room transcript hold the detail.
5. **Calm motion.** Small transitions, no looping animation, and full support for `prefers-reduced-motion`.

## Information Architecture

| View | Purpose | Primary content |
| :--- | :--- | :--- |
| **Overview** | Is this release ready or live? | Release title and approval line, five-step pipeline, What's shipping, three-row ship checklist |
| **Verify** | What proves it? | Sandbox check cards, filterable commit table, editorial contract findings |
| **Rooms** | What did the agents hand off? | Linked Switch rooms only, room switcher, full transcript, local demo composer |
| **Content** | What are we publishing? | DEV.to draft, changelog, social kit; preview/raw modes where they apply |
| **Artifacts** | What is in the bundle? | File list with sizes, line-numbered viewer, copy/download |

A sticky release strip under the header carries the repo, version, published/verified state, commit range, changes, importance, and publication date on every view.

## Layout

- **Shell:** max-width `1480px`, 28px desktop gutters; 10px gutters below 620px.
- **Header:** brand, one segmented nav, search, refresh, run, and publish. Below 1180px the nav moves to its own full-width row. Below 400px the brand wordmark hides and the logo remains.
- **Overview:** release run panel full width; below it a two-column grid for release commits and the ship checklist.
- **Verify:** two sandbox cards side by side above a two-column grid for the commit table and editorial contract.
- **Rooms:** a linked-room list and chat pane in one bordered shell; the list becomes a horizontal tray below 900px.
- **Content:** centered reading column for the draft and changelog; social posts use a two-column card grid that collapses to one column.
- **Artifacts:** a sticky file list beside a dark code surface; the list becomes a horizontal file tray below 1180px.

## Color

| Token | Value | Use |
| :--- | :--- | :--- |
| `--bg` | `#DEDCD3` | Outer stone canvas |
| `--canvas` | `#EFEEE7` | Soft page wash |
| `--card` | `#FFFFFF` | Cards, article, chat pane |
| `--card-2` | `#F7F6F0` | Inset rows and room list |
| `--card-3` | `#F1EFE7` | Pills and quiet fills |
| `--ink` | `#161614` | Headings, primary text, active nav |
| `--ink-2` | `#4E4D47` | Body copy |
| `--muted` | `#817F76` | Metadata and labels |
| `--line` | `#E4E1D7` | Hairlines and borders |
| `--lime` | `#D9F65A` | Done states, publish CTA, active room count |
| `--indigo` | `#4B45E8` | Links and copy actions |
| `--mint` | `#0E9F6E` | Passed checks and added commits |
| `--coral` | `#E2602A` | Filtered commits and warnings |
| `--violet` | `#7A5AF8` | Documentation and room links |
| `--blue` | `#2E6FE8` | Fixed commits |
| `--dark` | `#171715` | Pipeline panel and code viewer |

Semantic pills always pair color with a label (`Passed`, `Filtered`, `Published`, `Not posted yet`) so color is never the only signal.

## Typography

- **Display:** Instrument Serif, regular and italic. Used only for page titles and the release headline (`v0.2.0 is live.`). One display moment per view.
- **UI and body:** DM Sans, 400–700. 14px base, 12.5–13px in dense tables and cards.
- **Data:** JetBrains Mono, 9–12px. Commit SHAs, receipt hashes, commands, scores, dates, file sizes, and line numbers.
- **Eyebrows:** 9–10px uppercase mono with wide tracking. Used sparingly for section context.

Body copy uses generous line-height; data uses tabular numerals. Avoid all-caps body text and decorative letter-spacing outside the eyebrow style.

## Components

### Release pipeline
A single dark panel with five steps: Analyze, Verify, Validate, Bundle, Publish. Each step is a button that jumps to the relevant evidence or opens the publish flow. Done steps use a lime check; pending steps show their number. The receipt chip copies the full SHA. The voice note and transcript link sit in one footer row.

### Commit rows and table
Overview rows show subject, category, short SHA, date, and score. Verify adds type, diff counts, a score bar, and a copy-SHA action. Filters are All / Included / Filtered; search matches subject, SHA, or type. Filtered rows stay legible but recessed.

### Ship checklist
Exactly three rows: sandbox execution, editorial contract, human approval. Each row carries a derived status and a one-line explanation. The receipt hash and copy action sit at the bottom. Do not add more checklist rows without removing another.

### Sandbox cards
Check number, command, explicit pass/fail pill, duration, exit code, receipt hash, and a collapsed output disclosure. Errors take precedence over stdout in the disclosure.

### Rooms
Only rooms linked to ShipCast appear; generic `Welcome` and `New Chat` sessions are excluded. Setup chatter is hidden by default with a visible switch and a count of what was hidden. Messages show sender, handle, role, and sequence. The composer is explicitly a local demo: typing adds a message to this view, and `approve`/`run` opens the matching flow without pretending to post to Switch.

### Content
- **DEV.to draft:** frontmatter becomes a title, description, tag row, AI disclosure, and reading column. Publication status is labeled `Not posted yet` until the post itself is published to DEV — independent of the release publication state.
- **Changelog:** rendered markdown in the same reading column.
- **Social:** Copy actions are per platform and per post. Preview/raw and the toolbar copy action only appear for draft and changelog.
- Markdown preview supports headings, paragraphs, lists, blockquotes, fenced code with copy, inline code, links, bold, and italics. Raw mode always shows the exact source.

### Artifacts
Eight bundle files: both templates, DEV.to draft, changelog, social JSON, verification receipt, publication receipt, and room summary. The viewer shows exact text with line numbers. Copy and download act on the selected file.

### Command palette
Open with the search button, `⌘K`/`Ctrl+K`, or `/` outside an input. Search checks item titles, aliases, metadata, groups, commits, rules, artifacts, and rooms. Title matches rank above keyword and description matches. Arrow keys move, Enter opens, Escape closes.

### Modals and toast
Run pipeline: version, commit range, voice note with optional Web Speech dictation, and a warning that a passing run replaces `dist/latest`. Publish: a summary of release, included commits, checks, rules, and approver; the confirm action is disabled unless verification passes. Toast feedback is brief and announced through `aria-live`.

## State Rules

- **Verified** requires `verification_receipt.all_passed`, a valid contract report, and at least one check.
- **Published** requires a publication receipt whose version matches the bundle and whose `verification_receipt_sha256` matches the current verification receipt. A stale receipt for a previous or different bundle is not treated as live.
- **Counts** (commits, checks, rules, messages, files, durations) come from the bundle and transcript; nothing is estimated in the interface.
- **Loading failure** shows a console toast and leaves the shell in a readable empty state rather than inventing data.

## Responsive Behavior

| Breakpoint | Change |
| :--- | :--- |
| `1180px` | Nav takes its own row; overview/verify stack; artifact list becomes a horizontal tray |
| `900px` | Sandbox and social grids stack; rooms become list-over-chat; pipeline gap tightens and step details wrap |
| `620px` | Pipeline becomes a one-column list; compact header actions; article and modal padding tighten |
| `400px` | Brand wordmark hides, logo remains; header actions keep their labels |

No horizontal page overflow at 320px and above. Tables and code surfaces scroll inside their own containers.

## Accessibility

- Visible `:focus-visible` ring in indigo.
- Nav buttons expose `aria-current="page"`; icon-only actions have labels and titles.
- Modals use `role="dialog"` and `aria-modal`; Escape closes the palette or active modal; body scroll locks while an overlay is open.
- Release strip and toast are live regions.
- Decorative SVG icons are `aria-hidden`; copy actions describe what they copy.
- Reduced-motion preference disables meaningful animation.

## Anti-Slop Rules

- No duplicate top tabs and sidebar navigation.
- No KPI strips that repeat the same counts in different shapes.
- No fake media player, waveform, scrubber, or floating action dock.
- No hardcoded readiness percentage; derive it or omit it.
- No emoji as interface chrome; emoji in room transcript content is preserved as authored.
- No card inside a card inside a card. One border, one radius, one shadow level per surface.
- No placeholder controls that do not do something real.
