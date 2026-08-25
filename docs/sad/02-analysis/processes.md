# Quy trình (BPMN gọn)

## 1. Phiên học skeleton (Learner)

```
Start → Login (UC-L01) → Browse catalog (UC-L02)
  → Start session (UC-L03) → [optional: stay in shell]
  → End session (UC-L04) → Progress updated (UC-L05)
  → End
```

Lỗi: mất mạng khi end session → client retry; nếu fail, phiên `started` không cộng phút (không bịa duration). Không silent-drop.

## 2. Nhà máy nội dung (Teacher → publish)

```
Script brief (topic + ci_level)
  → Quay / thu
  → Upload media (UC-T03) + metadata draft (UC-T02)
  → Nộp Level QA (UC-T04)
  → Rubric (UC-Q01)
       ├─ Fail → sửa / quay lại (draft)
       └─ Pass → Admin publish (UC-A01)
  → API catalog có item
  → Ba client thấy (NFR-PERF-001)
```

Chi tiết thao tác: [SOP](../../content-ops/sop-pipeline.md).

## 3. Cấp quyền

Admin gán role (UC-A03). Teacher không publish nếu policy là chỉ Admin publish — v1: **Admin publish**; Teacher dừng ở `level_qa` sau khi QA pass (LevelQA có thể là Pedagogy). Nếu Sóng 1 ít người, một người kiêm Teacher+Admin phải vẫn đi hết trạng thái (không nhảy `draft` → `published` bỏ QA) trừ khi CEO ghi ngoại lệ có thời hạn.
