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

## Card trên board (Q1)

| # | Tiêu đề | Seat | Gate | FR / NFR |
|---|---|---|---|---|
| — | Scaffold monorepo theo ADR-001 | CTO | Platform | — |
| — | Sơ đồ SAD-2 và SAD-3 | BA | SAD-2 | — |
| — | 15 khung lo-fi web / phone / iPad | Design | SAD-3 | NFR-XPLAT-002 |
| — | Dựng board và quy ước card | CPO | Platform | — |
| [#2](https://github.com/quyendolearndata/JPLearn/issues/2) | Ký cổng SAD-1 (SRS) | CEO | SAD-1 | — |
| [#3](https://github.com/quyendolearndata/JPLearn/issues/3) | Ký cổng SAD-2 (Phân tích) | BA | SAD-2 | — |
| [#4](https://github.com/quyendolearndata/JPLearn/issues/4) | Ký cổng SAD-3 — năm chữ ký | CPO | SAD-3 | — |
| [#5](https://github.com/quyendolearndata/JPLearn/issues/5) | Viết OKR/KPI cho từng ghế Q1 | CPO | Platform | — |
| [#6](https://github.com/quyendolearndata/JPLearn/issues/6) | Merge PR #1 — agent theo ghế | CPO | Platform | — |
| [#7](https://github.com/quyendolearndata/JPLearn/issues/7) | Train rubric CI cho clip 1–2 | Pedagogy | Platform | — |
| [#8](https://github.com/quyendolearndata/JPLearn/issues/8) | Viết 10 brief clip level 0–1 | Teacher | Platform | — |
| [#9](https://github.com/quyendolearndata/JPLearn/issues/9) | Template release form | Ops | Platform | — |
| [#10](https://github.com/quyendolearndata/JPLearn/issues/10) | Privacy note staging | Ops | Platform | — |
| [#11](https://github.com/quyendolearndata/JPLearn/issues/11) | Trang positioning (không campaign) | Growth | Platform | — |
| [#12](https://github.com/quyendolearndata/JPLearn/issues/12) | Quay/thu 10–20 clip level 0–1 | Production | Platform | — |
| [#13](https://github.com/quyendolearndata/JPLearn/issues/13) | Chạy hết pipeline clip đầu tiên | Content | Platform | FR-CMS-002 |
| [#14](https://github.com/quyendolearndata/JPLearn/issues/14) | Playwright e2e API + web | QA | Platform | NFR-A11Y-001 |
| [#15](https://github.com/quyendolearndata/JPLearn/issues/15) | HLS trước cổng nền tảng | Platform | Platform | NFR-PERF-002 |
| [#16](https://github.com/quyendolearndata/JPLearn/issues/16) | Event payload vs dictionary | Data | Platform | FR-EVT-* |
| [#17](https://github.com/quyendolearndata/JPLearn/issues/17) | UC-L06 ba bề mặt | QA | Platform | FR-ID-002, FR-PRG-004 |

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
