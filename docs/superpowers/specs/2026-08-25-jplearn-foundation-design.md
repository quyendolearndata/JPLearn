# JPLearn Foundation Design Spec

Ngày: 2026-08-25  
Trạng thái: **artifact đủ để review và ký cổng** (use case, Mermaid, 15 khung lo-fi, OpenAPI). Platform đã scaffold trên `main`. Chưa vòng học Phase 5.  
Owner tổng: CPO + BA. Pedagogy bible là đầu vào, không thay SRS.

> Spec này gộp quyết định đã chốt. Chi tiết sống ở thư mục `docs/`. Đổi yêu cầu thì sửa SRS trước, rồi truy vết, rồi spec này.

## 1. Vấn đề và mục tiêu

Người lớn Việt học tiếng Nhật theo lớp/app JLPT/Anki thì nghe yếu; YouTube CI đúng hướng nhưng không phải hệ thống (cấp, giờ, đồng bộ, nhà máy nội dung). JPLearn dựng nền tảng để thụ đắc như trẻ: input dễ hiểu, silent period, tiến độ = phút CI + cấp — trên web, điện thoại, iPad.

North star và phạm vi: [docs/company/vision.md](../../company/vision.md).

**Gói này không xây app học đầy đủ.** Gói này khóa công ty + PT&TKHT + hợp đồng kỹ thuật + pipeline clip thí điểm.

## 2. Quyết định sản phẩm (không đàm phán v1)

- Tiến bộ = `minutes_comprehensible` + `current_ci_level`, không flashcard/JLPT.
- Dịch L1 không phải kênh hiểu nghĩa trên client học viên.
- Output nói tắt bằng flag, mặc định false.
- iPad lean-back, phone on-the-go, web lean-forward; cùng identity/API.
- Schema cấm: `vocabulary_score`, `grammar_lesson_id`, `translation_pair` kênh chính.

Bible: [docs/pedagogy/bible.md](../../pedagogy/bible.md). Taxonomy: [docs/pedagogy/taxonomy.md](../../pedagogy/taxonomy.md).

## 3. Tổ chức và quy trình

Org + sóng tuyển: [docs/company/org-and-hiring.md](../../company/org-and-hiring.md).  
RACI: [docs/company/raci.md](../../company/raci.md).  
Nhịp / DoR / DoD: [docs/company/operating-system.md](../../company/operating-system.md).  
OKR Q1: [docs/company/okr-q1.md](../../company/okr-q1.md).  
Backlog 90 ngày: [docs/company/90-day-backlog.md](../../company/90-day-backlog.md).  
Cổng ký: [docs/company/gates.md](../../company/gates.md).

BA sở hữu PT&TKHT. Engineering không scaffold trước cổng SAD-3.

## 4. SAD-1 — Yêu cầu

Khảo sát: [docs/sad/01-survey-srs/survey.md](../../sad/01-survey-srs/survey.md).  
Stakeholder: [docs/sad/01-survey-srs/stakeholders.md](../../sad/01-survey-srs/stakeholders.md).  
Feasibility: [docs/sad/01-survey-srs/feasibility.md](../../sad/01-survey-srs/feasibility.md).  
**SRS (nguồn sự thật FR/NFR):** [docs/sad/01-survey-srs/srs.md](../../sad/01-survey-srs/srs.md).

In: identity, catalog, session skeleton, progress giờ, CMS, flags, events, 3 client shell, 10–20 clip pipeline.  
Out: thư viện công khai, thanh toán, speaking, quiz, phụ đề L1, JLPT.

## 5. SAD-2 — Phân tích

Context: [docs/sad/02-analysis/context.md](../../sad/02-analysis/context.md).  
Use case + FR→UC: [docs/sad/02-analysis/use-cases.md](../../sad/02-analysis/use-cases.md).  
Quy trình phiên + nhà máy: [docs/sad/02-analysis/processes.md](../../sad/02-analysis/processes.md).  
Domain: [docs/sad/02-analysis/domain-model.md](../../sad/02-analysis/domain-model.md).  
Từ điển dữ liệu: [docs/sad/02-analysis/data-dictionary.md](../../sad/02-analysis/data-dictionary.md).

Actors v1: Learner (test), Teacher, LevelQA, Admin.

## 6. SAD-3 — Thiết kế

C4: [docs/sad/03-design/c4.md](../../sad/03-design/c4.md).  
ERD: [docs/sad/03-design/erd.md](../../sad/03-design/erd.md).  
OpenAPI: [docs/sad/03-design/openapi.yaml](../../sad/03-design/openapi.yaml).  
UI shell: [docs/sad/03-design/ui-shell.md](../../sad/03-design/ui-shell.md).  
Wireframe hình: [docs/sad/03-design/wireframes/README.md](../../sad/03-design/wireframes/README.md) — 15 khung SVG lo-fi (web / phone / iPad).
Sơ đồ: [SAD-2 diagrams](../../sad/02-analysis/diagrams.md), [SAD-3 diagrams](../../sad/03-design/diagrams.md).  
Deploy: [docs/sad/03-design/deployment.md](../../sad/03-design/deployment.md).  
Truy vết: [docs/sad/03-design/traceability.md](../../sad/03-design/traceability.md).  
ADR stack: [docs/sad/03-design/adr-001-stack.md](../../sad/03-design/adr-001-stack.md).

**Stack:** pnpm monorepo — `apps/web`, `apps/mobile`, `apps/api`, `packages/domain`, `packages/design-tokens`, `packages/cms-schema`. NestJS + Postgres. Expo cho iOS/iPad/Android. CMS v1 = `/staff` trên web.

**Luồng dữ liệu:** Client → API → DB; media file → storage; playback URL từ API. CMS publish đổi `status`; GET `/catalog` chỉ `published`. End session cộng phút + event.

**Lỗi:** login sai → 401; learner gọi staff → 403; end session fail mạng → retry, không bịa duration. Session zombie > 4 giờ không cộng phút.

**Kiểm thử:** cột Test trên ma trận; ưu tiên T-NEG (vắng flashcard/grammar/dịch) và T-ID-002 (3 bề mặt).

## 7. Nhà máy nội dung

SOP: [docs/content-ops/sop-pipeline.md](../../content-ops/sop-pipeline.md).  
CMS form: [docs/content-ops/cms-schema.md](../../content-ops/cms-schema.md).  
Không nhảy draft→published bỏ Level QA.

## 8. Phase và cổng

```
P0 Company OS → SAD-1 SRS → P1 Pedagogy + SAD-2
  → P2 IA + SAD-3 thiết kế → [cổng thiết kế] → P3 scaffold
  → P4 pipeline clip (song song P3)
  → [cổng nền tảng] → P5 SAD vòng học (FR-LRN-*)
```

P0–SAD-3 docs + sơ đồ + 15 khung lo-fi: **đã viết trong repo**.
P3 code: **đã scaffold trên `main`**. Cổng SAD vẫn cần chữ ký trên [gates.md](../../company/gates.md).
P5: spec riêng, lặp SAD thu hẹp.

Cổng nền tảng: bible ký; truy vết không lỗ FR v1; 3 client cùng catalog; publish ≤ NFR-PERF-001; event phút ghi được; quyền media sạch; tokens 3 bề mặt.

## 9. Rủi ro

| Rủi ro | Mitigation |
|---|---|
| Trượt textbook để “có demo” | FR-NEG, flags false, T-NEG, CEO từ chối |
| iPad = phone phóng to | NFR-XPLAT-002, DoD, 5 khung iPad |
| Scaffold trước hợp đồng | Cổng SAD-3 |
| Clip không phép | SOP bước 2, Ops |
| SRS bị bible thay | BA owner, hai tài liệu tách |

## 10. Self-review (2026-08-25)

- Placeholder: wireframe lo-fi đã có SVG; HLS = trước cổng nền tảng; probes = P5.
- Mâu thuẫn: player CI đầy đủ là P5; `playback_url` trên catalog vẫn có để CMS chứng minh media — shell v1 không bắt buộc player. MP4 Q1 vs HLS: ADR-001, không mâu thuẫn SRS.
- Phạm vi: một spec nền tảng, không nhét vòng học.
- Mơ hồ đã khóa: tiến độ = phút + cấp; publish = admin; session skeleton không cần video; role learner/teacher/admin.

## 11. Việc tiếp theo

Implementation plan scaffold: [docs/superpowers/plans/2026-08-25-jplearn-platform-foundation.md](../plans/2026-08-25-jplearn-platform-foundation.md).

Chưa làm: HLS, Phase 5 vòng học. Ký cổng trên [gates.md](../../company/gates.md) khi team chính thức.
