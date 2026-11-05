## [v0.2.0] - 2026-11-05

> Importance Score: **9/10** · Commits included: **4** (filtered 1 low-signal commits) · Verification Receipt: `d23ff7cf96db30bd`

### Release Context
Focus on the two-room Switch topology (#shipcast-studio-desk and #shipcast-verification-lab), cryptographic SHA-256 sandbox receipts, and human approval gate.

### Added
- **feat(templates): default provider to antigravity and working directory to shipcast repo** (`d02883b`, +22/-6) (`shipcast.template.yaml`, `shipcast.v2.template.yaml`)

### Fixed
- **fix(templates): remove  requirement so local unbridged Switch rooms enable Create all** (`985b6c5`, +5/-15) (`shipcast.template.yaml`, `shipcast.v2.template.yaml`)
- **fix(template-v2): add studio_group resource so v2 passes switch_core.template_lint with 0 errors** (`31c1f72`, +11/-0) (`shipcast.v2.template.yaml`)

### Documentation
- **docs(bundle): refresh dist/latest bundle across full commit range** (`58ab37d`, +419/-161) (`dist/latest/bundle-data.json`, `dist/latest/changelog-entry.md`, `dist/latest/changelog-seo.jsonld`)
