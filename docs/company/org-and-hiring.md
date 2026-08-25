# Tổ chức đích và sóng tuyển

Cơ cấu **có đủ ghế** ngay. Người thật điền dần. Một founder được giữ tối đa 3 ghế trong Sóng 1; ghế BA không được để trống (CEO/CPO kiêm cũng được, phải ghi rõ). Mỗi ghế có custom agent trong [`.cursor/agents/`](../../.cursor/agents/README.md).

## Sơ đồ

```
CEO
├── CPO
│   ├── BA / System Analyst     ← chủ PT&TKHT
│   ├── Head of Pedagogy
│   │   └── Pedagogy QA
│   └── Design Lead
├── Content Director
│   ├── Japanese Teachers
│   ├── Video / Audio Production
│   └── CI Level QA
├── CTO
│   ├── Platform / Backend
│   ├── Web
│   ├── Mobile (iOS, iPad, Android)
│   ├── Data / Analytics
│   └── QA Engineering
└── Growth
    ├── Community / CS
    └── Ops / Legal / Finance
```

## Trách nhiệm một dòng

| Vai | Làm gì | Không làm gì |
|---|---|---|
| CEO | Runway, ký cổng, giữ north star | Thêm feature textbook “cho nhanh” |
| CPO | Backlog bám SRS, từ chối lệch bible | Thay BA viết SRS |
| BA | Khảo sát, SRS, use case, truy vết | Nhảy cóc sang code |
| Pedagogy | Bible, thang cấp, rubric CI | Spec API |
| Design | Tokens, IA 3 bề mặt, shell | Grammar screens trước Phase 5 |
| Content Director | Nhà máy clip, CMS editorial | Tự publish vượt Level QA |
| CTO | C4, stack, hiện thực sau cổng | Scaffold trước SAD-3 |
| QA | Test case từ ma trận truy vết | Test “cảm tính” không mã FR |
| Growth | Im lặng ra thị trường ở Q1 | Mời học viên thật trước cổng nền tảng |

## Sóng tuyển

**Sóng 1 — nền tảng (4–8 FTE hoặc equivalent)**  
CEO, CPO/PM, BA, Head of Pedagogy, Design Lead, CTO, 1 Platform engineer, Content Director, 1 giáo viên bản ngữ part-time.

**Sóng 2 — khi skeleton chạy**  
Mobile, Web, Video/Audio, CI Level QA, QA engineer.

**Sóng 3 — trước học viên thật**  
Growth, CS, Data, Legal/Ops, thêm giáo viên và production.

Chi tiết task 90 ngày đầu: [raci.md](raci.md) và plan gốc.

**Custom agents:** mỗi ghế một agent — [`.cursor/agents/README.md`](../../.cursor/agents/README.md).
