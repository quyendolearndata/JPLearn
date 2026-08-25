# Bằng chứng issue #34 — đo contrast chrome learner (WCAG AA)

- Ghế: **QA Engineering** · Ngày: 2026-08-25 · Issue: [#34](https://github.com/quyendolearndata/JPLearn/issues/34)
- Test ID: **T-NFR-A1** (phần chrome AA) theo `docs/sad/03-design/traceability.md`; FR/NFR: `NFR-A11Y-001`
- Kết luận: **PASS phần contrast** trên 4 màn learner. Phần keyboard pause của player thuộc Phase 5 (control chưa tồn tại) — không nhét vào card này, đúng acceptance.

## Cách đo

`axe-core` (qua `axe-playwright`) chạy trong Playwright trên stack thật: API :3001 + web :3000 + Postgres embedded. Mỗi trang inject axe và chạy `checkA11y` với ruleset mặc định WCAG 2.x (A + AA, gồm `color-contrast`).

Màn đo (sau đăng ký tài khoản mới qua UI — đường learner thật):

| Màn | Route | Kết quả |
|---|---|---|
| Đăng nhập/Đăng ký | `/login` | Không vi phạm |
| Catalog | `/` | Không vi phạm |
| Phiên | `/session` | Không vi phạm |
| Tiến độ | `/progress` | Không vi phạm |

Bảng màu chrome hiện tại (`apps/web/src/app/globals.css`): nền `#f6f1e8`, chữ `#1c1917` (~14.9:1), link `#44403c` (~9.7:1) — đều vượt ngưỡng AA 4.5:1.

## Lệnh + output

```bash
cd apps/web && npx playwright test e2e/a11y.spec.ts   # cần API :3001 + web :3000 đang chạy
```

```
No accessibility violations detected!   (×4 — mỗi màn một lần)
✓ 1 e2e/a11y.spec.ts:20:5 › chrome learner đạt contrast WCAG AA T-NFR-A1 (1.6s)
1 passed (2.1s)
```

## Phát hiện phụ (không fail card này)

- axe báo `document-title` (serious): các trang chưa có `<title>` riêng. Đây là lỗi a11y thật nhưng **ngoài phạm vi contrast** — test tắt riêng rule này bằng `axeOptions.rules['document-title']`. Đề xuất CPO mở card a11y nhỏ (metadata title/description theo route) cho Web; không chặn #34.

## Files

- `apps/web/e2e/a11y.spec.ts` — test T-NFR-A1 (contrast).
- `apps/web/package.json` + `pnpm-lock.yaml` — devDeps `axe-core`, `axe-playwright`.

Không commit, không push (CPO ghép commit theo ghế).
