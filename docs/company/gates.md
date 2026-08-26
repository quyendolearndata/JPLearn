# Mẫu ký cổng

Sao chép khối dưới vào cuối artifact khi review. Không ký bằng miệng.

## Cổng SAD-1 — SRS

- Tài liệu: `docs/sad/01-survey-srs/srs.md`
- **Artifact:** có — SRS + in/out scope
- **Chữ ký:** đã ký 2026-08-25 — CPO, Pedagogy, CTO (issue #2)
- CPO: tên / ngày / đồng ý phạm vi in-out
- Pedagogy: tên / ngày / đồng ý ràng buộc cấm textbook
- CTO: tên / ngày / đồng ý NFR khả thi

## Cổng SAD-2 — Phân tích

- Tài liệu: `docs/sad/02-analysis/` + [diagrams.md](../sad/02-analysis/diagrams.md)
- **Artifact:** có — use case, diagrams, [event audit](../sad/02-analysis/event-payload-audit.md)
- **Chữ ký:** đã ký 2026-08-25 — BA, Pedagogy, CTO (issue #3)
- BA: mọi FR nền tảng map ≥1 use case
- Pedagogy: domain không chứa điểm ngữ pháp/từ vựng như tiến độ
- CTO: domain hiện thực được bằng Hướng A

## Cổng SAD-3 — Thiết kế (được phép scaffold)

- Tài liệu: `docs/sad/03-design/` + spec tổng hợp + [diagrams](../sad/03-design/diagrams.md) + [15 khung](../sad/03-design/wireframes/README.md)
- **Artifact:** có — scaffold + wireframes merged
- **Chữ ký:** đã ký 2026-08-25 — CEO, CPO, BA, Pedagogy, CTO (issue #4)
- CEO, CPO, BA, Pedagogy, CTO: năm chữ ký
- Điều kiện: truy vết FR/NFR → use case → API/bảng → test ID

## Cổng nền tảng — được phép SAD vòng học (Phase 5)

- Tài liệu: spec §8 + [traceability](../sad/03-design/traceability.md) + board #12–#17
- **Phiên ký:** CEO mở 2026-08-25 (rút HOLD). Không ký miệng.
- **Người ký:** CEO, CPO, Pedagogy, CTO (`docs/README.md`)
- **Điều kiện (spec):** bible; truy vết FR v1; 3 client cùng catalog; publish ≤ NFR-PERF-001; event phút; quyền media; tokens 3 bề mặt
- **Cấm sau khi ký:** flashcard, dịch L1-as-meaning, grammar drill như “thử nghiệm nhỏ” (FR-NEG). Flags `speaking_enabled` / `l1_subtitles_enabled` / `grammar_enabled` / `flashcards_enabled` **giữ false** đến khi Pedagogy bật có chủ đích.

### Checklist phiên này

| Điều kiện | Hiện trạng |
|---|---|
| Shell 3 bề mặt + CMS publish + sự kiện phút | **Đạt** — web + API; #13 pipeline; #14 e2e; #16 events |
| 10 clip thí điểm + quyền | **Đạt thí điểm** — #12 Veo/Commons + Kyoko; không phải 70–95s người thật |
| HLS trên web và iPad (NFR-PERF-002) | **Đã đóng phía web 2026-08-25/26** — CiPlayer hls.js + fallback MP4 (#31); #40 vá nosniff + ký segment trong manifest → e2e PASS cả Chromium lẫn WebKit (Chromium phát HLS thật, không rớt MP4); iPad native player có code (expo-video) chờ verify máy thật (#30) |
| Playback URL đã ký (FR-CMS-003/004) | **Đã đóng 2026-08-25** — HMAC `exp`+`sig` trên playback/hls URL (#24, T-CMS-003 PASS); #35 thêm guard publish thiếu media + unpublish; #39 seed không còn tái tạo item ma |
| UC-L06 native iPhone/iPad/Android | **Exception** — PASS API + web; native PARTIAL (#17), theo dõi #30 (config EAS dev build + checklist đã sẵn sàng 2026-08-26, chờ Expo login + Apple Developer của founder) |
| NFR-OBS 5xx alert; NFR-A11Y đo | **A11Y đã đóng 2026-08-26** — request id + log 5xx JSON (#25); contrast AA PASS (#34); document-title PASS (#36); còn nợ duy nhất: alert staging thật (#38, đang làm) |

Nợ exception = việc Platform/Mobile/QA **sau cổng**, không chặn SAD vòng học. Không dùng exception để mở FR-NEG.

**Chữ ký:** đủ bốn ghế 2026-08-25 (khối dưới).

---

## Chữ ký (2026-08-25)

### Cổng SAD-1
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi in/out SRS
- Pedagogy — Quyen Do — 2026-08-25 — Đồng ý ràng buộc cấm textbook
- CTO — Quyen Do — 2026-08-25 — Đồng ý NFR khả thi

### Cổng SAD-2
- BA — Quyen Do — 2026-08-25 — Mọi FR nền tảng map ≥1 use case
- Pedagogy — Quyen Do — 2026-08-25 — Domain không có điểm ngữ pháp/từ vựng như tiến độ
- CTO — Quyen Do — 2026-08-25 — Domain hiện thực được bằng Hướng A

### Cổng SAD-3
- CEO — Quyen Do — 2026-08-25 — Đồng ý scaffold theo thiết kế
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi scaffold
- BA — Quyen Do — 2026-08-25 — Truy vết FR/NFR → UC → API/bảng → test
- Pedagogy — Quyen Do — 2026-08-25 — Shell không vi phạm bible
- CTO — Quyen Do — 2026-08-25 — ADR-001 + OpenAPI + schema đúng

### Cổng nền tảng
- CEO — Quyen Do — 2026-08-25 — Mở phiên ký; rút HOLD; chấp nhận exception HLS/URL ký/UC-L06 native; cấm FR-NEG; được phép SAD vòng học (Phase 5), không tự bật flag
- CPO — Quyen Do — 2026-08-25 — Đồng ý phạm vi nền tảng; card `FR-LRN-*` được vào board sau cổng này; không flashcard/JLPT
- Pedagogy — Quyen Do — 2026-08-25 — Shell không textbook; clip Veo 10s không thay bible 70–95s; silent period đến khi bật `speaking_enabled`
- CTO — Quyen Do — 2026-08-25 — Schema không cột cấm; HLS/object storage/URL ký ghi nợ exception, không tuyên bố NFR-PERF-002 đã đủ hardware production
