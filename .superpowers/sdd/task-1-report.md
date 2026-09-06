# Báo cáo Task 1 — BA/QA mở lại C4

## What you implemented

- Chuyển recovery follow-up sang **IN PROGRESS** và ghi baseline review `c2329a5`.
- Mở lại C4 trong kế hoạch remediation, nêu rõ F-01–F-03 cần evidence mới; không
  mở lại R-01, R-02 hoặc R-04.
- Cập nhật walkthrough và evidence để phân biệt remediation đang chạy với số liệu
  lịch sử tại `fd838d2`: pytest 217, Playwright 21+21, web unit 7.
- Ghi chú C5 keyboard/manual vẫn **PARTIAL**.
- Cập nhật closeout và implementation plan: Mốc A recovery chưa đóng; Mốc B giữ
  kết quả hồi quy, không dựng lại workflow.
- Bổ sung scenario F-01–F-04 vào các hàng FR/NFR hiện có trong traceability,
  không đổi FR/UC/Test ID.

## What you tested

- Không chạy runtime test theo phạm vi tài liệu-only.
- Đã kiểm tra consistency bằng `git diff --check` và rà các trạng thái,
  baseline SHA, F-01–F-04, C4/C5 trên các tài liệu đã sửa.

## Files changed

- `walkthrough.md`
- `docs/superpowers/plans/2026-09-06-web-frontend-remediation.md`
- `docs/superpowers/plans/2026-09-06-web-frontend-recovery-followup.md`
- `docs/qa/remediation-evidence-2026-09-06.md`
- `docs/superpowers/plans/2026-09-06-remediation-closeout.md`
- `docs/superpowers/plans/2026-09-06-web-frontend-implementation.md`
- `docs/sad/03-design/traceability.md`
- `.superpowers/sdd/task-1-report.md`

## Self-review findings

- Không sửa `apps/web`, `apps/api-python`, schema hoặc API.
- Không tạo FR/UC/Test ID mới; các scenario được gắn vào hàng traceability hiện có.
- Số liệu lịch sử 217 / 21+21 / 7 và SHA `fd838d2` được giữ nguyên.
- Không còn tuyên bố C4 recovery đã đóng trong các tài liệu trạng thái hiện hành.

## Issues or concerns

- F-01–F-04 vẫn chưa được triển khai hoặc nghiệm thu; đây là chủ ý của Task 1.
- C5 keyboard/manual vẫn cần QA/Design cung cấp evidence trước khi đóng.
# Task 1 Report: Monorepo, domain package, forbidden-schema guard

## What was implemented

- **pnpm monorepo** at `.worktrees/feat-platform-foundation` with root `package.json`, `pnpm-workspace.yaml`, `tsconfig.base.json`, and updated `.gitignore`.
- **`@jplearn/domain`** — all types from the plan file map (`Role`, `DeviceClass`, `CiLevel`, `MediaType`, `VisualSupport`, `CatalogStatus`, `EventType`, `UserPublic`, `AuthSession`, `CatalogItemPublic`, `LearnerProgress`, `Flags`, `DEFAULT_FLAGS`, `ZOMBIE_SESSION_SECONDS`, `minutesFromDuration`).
- **`@jplearn/design-tokens`** — `tokens` constant per brief.
- **`@jplearn/cms-schema`** — `catalogWriteFields` constant per brief.
- **`scripts/assert-no-textbook.ts`** — FR-NEG-001/002/004 guard scanning `apps/` and `packages/` for banned strings.
- Root scripts: `test:guard`, `test` (guard + recursive package tests).

## What was tested and test results

| Command | Result |
|---------|--------|
| `pnpm --filter @jplearn/domain test` | PASS — 2 tests |
| `pnpm test:guard` | PASS — no banned strings |
| `pnpm test` | PASS — guard + domain tests |

## TDD Evidence

### RED

```bash
cd .worktrees/feat-platform-foundation && npx pnpm@9.15.0 install && npx pnpm@9.15.0 --filter @jplearn/domain test
```

```
FAIL src/index.test.ts
  ● Test suite failed to run
    src/index.test.ts:1:76 - error TS2307: Cannot find module './index' or its corresponding type declarations.
Test Suites: 1 failed, 1 total
Tests:       0 total
```

### GREEN

```bash
npx pnpm@9.15.0 --filter @jplearn/domain test && npx pnpm@9.15.0 test:guard && npx pnpm@9.15.0 test
```

```
PASS src/index.test.ts
  ✓ FR-FLG-001 flags default false
  ✓ FR-PRG-001 minutes floor; zombie adds zero
Test Suites: 1 passed, 1 total
Tests:       2 passed, 2 total

(test:guard — exit 0, no output)

(full test — exit 0)
```

## Files changed

| Path | Action |
|------|--------|
| `package.json` | Created |
| `pnpm-workspace.yaml` | Created |
| `pnpm-lock.yaml` | Created |
| `tsconfig.base.json` | Created |
| `.gitignore` | Updated |
| `packages/domain/package.json` | Created |
| `packages/domain/tsconfig.json` | Created |
| `packages/domain/jest.config.cjs` | Created (required for Jest; not listed in brief) |
| `packages/domain/src/index.ts` | Created |
| `packages/domain/src/index.test.ts` | Created |
| `packages/design-tokens/package.json` | Created |
| `packages/design-tokens/src/index.ts` | Created |
| `packages/cms-schema/package.json` | Created |
| `packages/cms-schema/src/index.ts` | Created |
| `scripts/assert-no-textbook.ts` | Created |

## Self-review findings

- **Completeness:** All brief-specified files created; domain exports match plan file map verbatim.
- **TDD:** RED confirmed missing `./index`; GREEN after implementation.
- **YAGNI:** No extra features beyond brief scope. Added only infrastructure required to run tests (`jest.config.cjs`, `devDependencies` for `tsx`/`jest`/`ts-jest`, `tsconfig.base.json` content inferred from tech stack since brief did not specify).
- **Quality:** `minutesFromDuration` handles zombie (>4h), negative, and floor division per FR-PRG-001.
- **Minor:** ts-jest emits TS151002 warning about `isolatedModules` with NodeNext — harmless for now; Task 2+ may tighten tsconfig.

## Issues or concerns

1. **`pnpm` not on PATH** — used `npx pnpm@9.15.0` for install/test; CI/local dev should ensure pnpm 9.15.0 via `corepack` or global install.
2. **Brief omitted Jest/tsconfig details** — `jest.config.cjs`, domain `devDependencies`, and root `tsx` devDependency were inferred as necessary; not explicitly in brief but required for `pnpm --filter @jplearn/domain test` to work.
3. **`pnpm-lock.yaml`** included in commit (not in brief's `git add` list) for reproducible installs.
