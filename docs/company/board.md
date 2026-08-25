# Board — quản lý task theo ghế

Board: **JPLearn Platform** — https://github.com/users/quyendolearndata/projects/1  
Owner (admin, ưu tiên, đóng cột): **CPO**. Không ghế nào khác tự đổi ưu tiên.

Chọn GitHub Projects thay Linear vì bằng chứng DoD (PR, commit, test) nằm cùng chỗ với card, và agent thao tác được bằng `gh` sẵn có.

## Field

| Field | Dùng để |
|---|---|
| `Status` | Todo / In Progress / Done |
| `Seat` | Một trong 19 ghế — khớp [`.cursor/agents/`](../../.cursor/agents/README.md) |
| `FR id` | Mã SRS (`FR-*` / `NFR-*`). Bắt buộc với task kỹ thuật |
| `Surface` | web / phone / iPad / CMS / API / docs / media |
| `Gate` | SAD-1 / SAD-2 / SAD-3 / Platform / Phase 5 |

`Seat` là **ghế chịu trách nhiệm**, không phải người. Sóng 1 một người giữ nhiều ghế; card vẫn ghi ghế để RACI không nhoè.

## Card hợp lệ

Definition of Ready ([operating-system.md](operating-system.md)) dịch sang field:

1. Owner → `Seat`
2. Tiêu chí chấp nhận → body của issue
3. Bề mặt ảnh hưởng → `Surface`
4. Mã SRS nếu là việc kỹ thuật → `FR id`
5. Không vi phạm [bible](../pedagogy/bible.md) → không có card nào tạo kênh flashcard / ngữ pháp / dịch L1

Card kỹ thuật thiếu `FR id` thì CPO trả về, không kéo vào sprint. Đây là KR2 của O1 trong [okr-q1.md](okr-q1.md).

## Việc gì **không** lên board

Điều cấm và ranh giới vai (“Growth im lặng Q1”, “Teacher không publish”) sống trong prompt của agent, không thành card. Board chỉ chứa việc có điểm kết thúc.

## Vòng đời một card

```
CPO tạo card (Seat + FR id)
  → mở chat với agent đúng ghế
  → làm việc, commit ghi mã FR
  → PR link issue (Closes #n)
  → QA đối chiếu cột Test trên ma trận truy vết
  → Done
```

Card cổng (`Gate`) chỉ Done khi chữ ký đã ghi trong [gates.md](gates.md) — không Done bằng cảm tính.

## Lệnh hay dùng

```bash
# xem việc của một ghế
gh project item-list 1 --owner quyendolearndata --format json

# tạo card kỹ thuật
gh issue create --repo quyendolearndata/JPLearn --title "..." --body "..."
gh project item-add 1 --owner quyendolearndata --url <issue-url>
```

Board đang ở chế độ private dù repo public. CPO mở public nếu cần chia sẻ ra ngoài.
