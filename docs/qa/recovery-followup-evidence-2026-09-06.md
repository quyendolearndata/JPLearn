# Recovery follow-up evidence — 2026-09-06

- **Ghế:** QA Engineering (`jplearn-qa`)
- **Plan:** [2026-09-06-web-frontend-recovery-followup.md](../superpowers/plans/2026-09-06-web-frontend-recovery-followup.md) §7 bước 6
- **Candidate SHA:** `41a4009fed53f8ff43bf5527a16d0976993293ff` (HEAD trước evidence commit)
- **Branch:** `codex/fastapi-backend-hardening`
- **Status:** **engineering PASS** — mọi lệnh bắt buộc exit 0. Không tuyên bố production/release. BA đóng plan/walkthrough/traceability sau số liệu này.
- **Test IDs:** T-NEG-001–004, T-SES-REC-001, T-LRN-001, T-NFR-A1, T-NFR-P2, T-FLG-002, T-CAT-002, T-CMS-E2E-001, T-AUTH-SEC-001, T-AUTH-ERR-001. Kịch bản F-01–F-04.

## Environment

- macOS 26.6.2 (darwin 25.6.0 / 25G83)
- Node 25.8.1, pnpm 9.15.0
- Host `python3` 3.14.2; API `uv` Python 3.12.13; pytest 9.1.1
- Playwright 1.62.1 — Chromium + **WebKit engine** (không phải Safari/iPhone/iPad thật)
- Isolated API/E2E DB: `/jplearn_test` (Compose project `jplearn-web-e2e-*`). Volume `jplearn_postgres_data` và media/dev **không** reset.
- Config sanitized: JWT/DB passwords không xuất hiện trong raw logs (xem `redact-note.txt`).

Raw logs: `docs/qa/evidence/recovery-followup-20260906-170905/`

| File | Nội dung |
|---|---|
| `sha.txt` / `dirty-before.txt` / `dirty-after.txt` | Candidate SHA; working tree sạch trước evidence; chỉ evidence docs sau chạy |
| `sw_vers.txt` `node.version` `pnpm.version` `python.version` `uv-python.version` `playwright.version` | Phiên bản |
| `guard.log` `web-unit.log` `web-build.log` `pytest.log` `e2e-chromium.log` `e2e-webkit.log` | Raw logs |
| `*.meta` `commands.tsv` | Exit + duration |
| `containers-before.txt` `containers-after.txt` `procs-after.txt` | Leftover E2E = 0 |

## Command table

| Command | Exit | Count | Duration | Log |
|---|---|---|---|---|
| `git rev-parse HEAD` + `git status --porcelain` | 0 | SHA `41a4009fed53f8ff43bf5527a16d0976993293ff`; dirty-before empty | <1s | `sha.txt`, `dirty-before.txt` |
| `pnpm test:guard` | 0 | 0 banned textbook fields | 0.480s | `guard.log` |
| `pnpm --filter @jplearn/web test` | 0 | tsc 0 errors; **35 passed**, 0 failed | 1.132s | `web-unit.log` |
| `pnpm --filter @jplearn/web build` | 0 | 10 routes | 7.543s | `web-build.log` |
| `pnpm test:api` | 0 | **217 passed**, 2 warnings (pytest 31.46s) | 32.436s | `pytest.log` |
| `web-e2e-python.sh --project=chromium` | 0 | **42 passed** (Playwright 2.3m) | 148.044s | `e2e-chromium.log` |
| `web-e2e-python.sh --project=webkit` | 0 | **42 passed** (Playwright 2.3m) | 147.639s | `e2e-webkit.log` |

Không skip. Không BLOCKED. Leftover `jplearn-web-e2e-*` sau mỗi run: 0. `next start` harness: 0.

## F-01–F-04 (engineering)

| ID | Trace | Engineering | Design | Ghi chú |
|---|---|---|---|---|
| F-01 | FR-SES-001/003, UC-L03, T-SES-REC-001 | **PASS** | — | Recovery E2E (pending GET, network/500, replay key, 409/401/403/404, late response) + unit T-SES-REC-001 |
| F-02 | FR-SES-002, FR-PRG-001/002, UC-L04/L05, T-SES-REC-001 | **PASS** | — | Ended path: lost end → GET ended → real summary; progress 500/offline không số giả, không POST end lần hai (3 E2E + 3 unit) |
| F-03 | FR-LRN-001, FR-CMS-003, FR-CAT-002, T-LRN-001 | **PASS** | — | Item lock + refresh budget (6 recovery E2E + 5 unit). **WebKit `hls.spec.ts` PASS** = native HLS trên **engine WebKit**, không phải thiết bị iPhone/Safari thật. Chromium `hls.spec.ts` cũng PASS (4 tests/engine gồm T-NFR-P2 + 3 F-03) |
| F-04 | NFR-A11Y-001, S-LOGIN/S-SESSION, T-NFR-A1 | **PASS** | **PARTIAL** | axe 8 routes + error/active/summary/staff-detail; keyboard Tab→Phát/Tạm dừng + `role=alert`. Native media keys: `tab-to-video=false`, `spaceChangedPaused=false` trên cả hai engine. Chưa rà Safari/iPhone/iPad thật; không claim WCAG 2.2 AA |

Annotation F-04 (cả hai engine):

```
[F-04] chromium tab-to-video=false; spaceChangedPaused=false; tab-from-catalog; stayed-on-control
[F-04] webkit    tab-to-video=false; spaceChangedPaused=false; tab-from-catalog; stayed-on-control
```

T-NEG: `pnpm test:guard` 0 banned fields; `tests/test_neg.py` trong 217 API; `shell.spec.ts` T-NEG-002 / T-FLG-002 trên Chromium + WebKit.

## Chữ ký QA

- QA (`jplearn-qa`): **PASS** theo bảng lệnh tại SHA trên. F-01–F-03 engineering PASS. F-04 engineering PASS + Design PARTIAL.
- Không đóng plan §8 / walkthrough COMPLETED từ ghế này.
- PASS local/test không mở production gate.
