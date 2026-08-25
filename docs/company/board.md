# Board — quản lý task theo ghế

Board: **[JPLearn Platform](https://github.com/users/quyendolearndata/projects/1)**  
Admin / ưu tiên: **CPO**. Ghế khác không tự đổi thứ tự cột.

GitHub Projects (không Linear) vì PR, CI và card cùng một chỗ; agent và `gh` thao tác được.

## Field trên board

| Field | Ý nghĩa |
|---|---|
| **Status** | Todo → In Progress → Done |
| **Seat** | Một trong 19 ghế — khớp [`.cursor/agents/`](../../.cursor/agents/README.md) |
| **FR id** | `FR-*` / `NFR-*` — **bắt buộc** task kỹ thuật (KR2 O1) |
| **Surface** | web / phone / iPad / CMS / API / docs / media |
| **Gate** | SAD-1 / SAD-2 / SAD-3 / Platform / Phase 5 |

**Seat** = ghế chịu trách nhiệm (RACI), không phải tên người. Sóng 1 một người kiêm nhiều ghế; card vẫn ghi ghế.

Field **đã được gán trên từng card** (Seat, Gate, Surface, FR id khi có). GitHub mặc định **chỉ hiện cột Status** — phải bật thêm cột trong view (xem mục dưới). Field custom **không** nằm trong body issue; mở card hoặc bảng Table mới thấy.

## Hiển thị Seat / Gate / Surface / FR id trên UI

GitHub Projects không tự show mọi custom field. Nếu board chỉ thấy **Status**, dữ liệu vẫn có — view chưa bật cột.

### Cách 1 — Table (nên dùng hàng ngày)

1. Mở [JPLearn Platform](https://github.com/users/quyendolearndata/projects/1).
2. Tab **Table** (không phải Board).
3. Góc phải bảng → **+** hoặc **Customize** / **Fields**.
4. Bật: **Seat**, **Gate**, **Surface**, **FR id** (và **Assignees** nếu gán người thật).
5. (Tuỳ chọn) **Save view** → đặt tên `By seat` hoặc `Full fields`.

Lọc theo ghế: filter `Seat = BA` (hoặc Teacher, Platform, …).

### Cách 2 — Board (kanban)

View **Board** group theo **Status** (Todo / In Progress / Done). Seat/Gate **không** thành cột kanban mặc định.

- Click một card → panel phải → cuộn **Seat**, **Gate**, **Surface**, **FR id**.
- Muốn nhìn nhiều ghế cùng lúc → dùng **Table**, không dùng Board.

### Cách 3 — CLI (kiểm tra nhanh)

```bash
gh project item-list 1 --owner quyendolearndata --format json
```

Mỗi item có `seat`, `gate`, `surface`, `status`. Ví dụ issue #2: Seat **CEO**, Gate **SAD-1**, Surface **docs**.

**FR id** bắt buộc trên task kỹ thuật (#14–#17, #24–#28, #30–#31, #34). Card cổng, OKR, clip brief, rubric để trống FR id là đúng.

## Card trên board (Q1)

| # | Tiêu đề | Seat | Gate | FR / NFR | Ghi chú |
|---|---|---|---|---|---|
| [#21](https://github.com/quyendolearndata/JPLearn/issues/21) | Scaffold monorepo theo ADR-001 | CTO | Platform | — | **Done** |
| [#20](https://github.com/quyendolearndata/JPLearn/issues/20) | Sơ đồ SAD-2 và SAD-3 | BA | SAD-2 | — | **Done** |
| [#19](https://github.com/quyendolearndata/JPLearn/issues/19) | 15 khung lo-fi web / phone / iPad | Design | SAD-3 | NFR-XPLAT-002 | **Done** |
| [#18](https://github.com/quyendolearndata/JPLearn/issues/18) | Dựng board và quy ước card | CPO | Platform | — | **Done** |
| [#2](https://github.com/quyendolearndata/JPLearn/issues/2) | Ký cổng SAD-1 (SRS) | CEO | SAD-1 | — | **Done** 2026-08-25 |
| [#3](https://github.com/quyendolearndata/JPLearn/issues/3) | Ký cổng SAD-2 (Phân tích) | BA | SAD-2 | — | **Done** 2026-08-25 |
| [#4](https://github.com/quyendolearndata/JPLearn/issues/4) | Ký cổng SAD-3 — năm chữ ký | CPO | SAD-3 | — | **Done** 2026-08-25 |
| [#23](https://github.com/quyendolearndata/JPLearn/issues/23) | Ký cổng nền tảng | CEO | Platform | — | **Done** 2026-08-25 (`gates.md`, kèm exception) |
| [#5](https://github.com/quyendolearndata/JPLearn/issues/5) | Viết OKR/KPI cho từng ghế Q1 | CPO | Platform | — | **Done** |
| [#6](https://github.com/quyendolearndata/JPLearn/issues/6) | Merge PR #1 — agent theo ghế | CPO | Platform | — | **Done** |
| [#7](https://github.com/quyendolearndata/JPLearn/issues/7) | Train rubric CI cho clip 1–2 | Pedagogy | Platform | — | **Done** |
| [#8](https://github.com/quyendolearndata/JPLearn/issues/8) | Viết 10 brief clip level 0–1 | Teacher | Platform | — | **Done** (10/10) |
| [#9](https://github.com/quyendolearndata/JPLearn/issues/9) | Template release form | Ops | Platform | — | **Done** |
| [#10](https://github.com/quyendolearndata/JPLearn/issues/10) | Privacy note staging | Ops | Platform | — | **Done** |
| [#11](https://github.com/quyendolearndata/JPLearn/issues/11) | Trang positioning (không campaign) | Growth | Platform | — | **Done** |
| [#12](https://github.com/quyendolearndata/JPLearn/issues/12) | Quay/thu 10–20 clip level 0–1 | Production | Platform | — | **Done** (10 MP4 Veo+Commons + Kyoko, docs/qa/issue-12-clips.md) |
| [#13](https://github.com/quyendolearndata/JPLearn/issues/13) | Chạy hết pipeline clip đầu tiên | Content | Platform | FR-CMS-002 | **Done** (stock+TTS, docs/qa/issue-13-pipeline.md) |
| [#14](https://github.com/quyendolearndata/JPLearn/issues/14) | Playwright e2e API + web | QA | Platform | NFR-A11Y-001 | **Done** (bfff7cf) |
| [#15](https://github.com/quyendolearndata/JPLearn/issues/15) | HLS trước cổng nền tảng | Platform | Platform | NFR-PERF-002 | **Done** (5c8dafa) |
| [#16](https://github.com/quyendolearndata/JPLearn/issues/16) | Event payload vs dictionary | Data | Platform | FR-EVT-* | Done (audit doc) |
| [#17](https://github.com/quyendolearndata/JPLearn/issues/17) | UC-L06 ba bề mặt | QA | Platform | FR-ID-002, FR-PRG-004 | **Done** (c5a3667, partial native) |
| [#24](https://github.com/quyendolearndata/JPLearn/issues/24) | HMAC signed playback URL | Platform | Platform | FR-CMS-003, FR-CMS-004 | **Done** (0b9e3df) |
| [#25](https://github.com/quyendolearndata/JPLearn/issues/25) | Request id + log 5xx | Platform | Platform | NFR-OBS-001 | **Done** (5ee91ed; alert staging = nợ) |
| [#26](https://github.com/quyendolearndata/JPLearn/issues/26) | useFlags chrome web | Web | Platform | FR-FLG-002 | **Done** (0a58c6d) |
| [#27](https://github.com/quyendolearndata/JPLearn/issues/27) | Player CI trong phiên web | Web | Phase 5 | FR-LRN-001 | **Done** web (2019ef2; Expo theo #31/nhánh mobile-player) |
| [#28](https://github.com/quyendolearndata/JPLearn/issues/28) | Padding iPad Phiên/Tiến độ | Mobile | Platform | NFR-XPLAT-002 | **Done** (ea73d5f; visual thật ở #30) |
| [#29](https://github.com/quyendolearndata/JPLearn/issues/29) | Cột trạng thái ma trận truy vết | BA | Platform | — | **Done** (ad81452) |
| [#30](https://github.com/quyendolearndata/JPLearn/issues/30) | UC-L06 máy native founder | QA | Platform | FR-ID-002, FR-PRG-004 | **Todo** — cần máy thật founder |
| [#31](https://github.com/quyendolearndata/JPLearn/issues/31) | Phát HLS trên web | Web | Platform | NFR-PERF-002 | **In Progress** — nhánh feat/web-hls-player |
| [#32](https://github.com/quyendolearndata/JPLearn/issues/32) | Review rubric CI clip thí điểm | Pedagogy | Platform | — | **Done** (99ba8fc; batch PASS) |
| [#33](https://github.com/quyendolearndata/JPLearn/issues/33) | Pass/fail 10 clip stock | CI Level QA | Platform | — | **Done** (e54b7d3; 10/10 PASS, nợ workflow level_qa) |
| [#34](https://github.com/quyendolearndata/JPLearn/issues/34) | Đo contrast chrome AA | QA | Platform | NFR-A11Y-001 | **Done** (6620630; nợ document-title) |

Định hướng theo phòng (không phải từng card): [90-day-backlog.md](90-day-backlog.md).

## Definition of Ready → field

1. Owner → **Seat**
2. Tiêu chí chấp nhận → body issue (template [platform-task](../../.github/ISSUE_TEMPLATE/platform-task.yml))
3. Bề mặt → **Surface**
4. Mã SRS (task kỹ thuật) → **FR id**
5. Không vi phạm [bible](../pedagogy/bible.md)

Card kỹ thuật thiếu **FR id** → CPO trả về, không vào sprint.

## Việc **không** lên board

Ranh giới vai (“Growth im lặng Q1”, “Teacher không publish”) nằm trong prompt agent, không thành card.

## Vòng đời

```
CPO tạo issue + thêm lên board (Seat + FR id)
  → chat agent đúng ghế
  → PR ghi FR, Closes #n
  → QA đối chiếu ma trận truy vết
  → Status = Done
```

Card **Gate** chỉ Done khi chữ ký ghi trong [gates.md](gates.md).

## Lệnh

```bash
# tạo task
gh issue create --repo quyendolearndata/JPLearn \
  --template platform-task.yml

# thêm lên board
gh project item-add 1 --owner quyendolearndata --url https://github.com/quyendolearndata/JPLearn/issues/NN

# xem card theo ghế (JSON)
gh project item-list 1 --owner quyendolearndata --format json
```

Board hiện **private**; repo public. CPO có thể đổi visibility project nếu cần chia sẻ.
