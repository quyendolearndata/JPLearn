# ADR-006 — CMS draft editing and recorded Level QA

Status: implementation proposal for review on `codex/jplearn-development`.
Requested by founder in this session; no historical gate signatures are changed.
BA scope: FR-CAT-005, FR-CMS-001/002, NFR-SEC-002; UC-T02/T03/T04/Q01/Q02/A01.

## Contract and policy

- Teacher/Admin collaborate on all staff items, matching existing mutation permissions.
- GET /staff/catalog: optional status filter, limit 1–100 (default 50), offset >= 0; stable id order.
- GET /staff/catalog/{id}: metadata, media playback links and internal review history.
- PATCH /staff/catalog/{id}: draft only; at least one non-null metadata field; reject unknown fields.
- POST /staff/catalog/{id}/review: Teacher/Admin records approve or reject once per submission.
  Notes are trimmed, maximum 2000 characters; reject requires a nonempty reason.
  Reviewer comes from authentication, never the request body. Teacher may review own work
  as permitted by the existing combined Teacher/LevelQA role; this is not independent review.
- submit-qa increments qa_round. Reject returns to draft; approve keeps level_qa.
- publish stays Admin-only and requires approval for the current round plus existing media checks.
- Metadata, upload and HLS registration are draft-only, so an approved submission cannot change.
- Catalog mutations lock the same catalog row, serializing edits, review, upload and publish.
- Unpublish returns to draft. Resubmission requires a new review; old reviews remain staff-only.
- Existing published items remain visible after migration. Existing level_qa items need a recorded
  review in round 0 before publish. No approval evidence is invented during migration.

## Schema / rollout

Alembic 0002_cms_reviews adds catalog_items.qa_round and catalog_reviews (one verdict per round).
Reviewer FK, decision/rejection-note checks, and unique item/round enforce the audit record.
Run migration before starting new API workers; deploy the API as one version (do not leave old
workers able to publish without approval). The existing staff shell receives explicit approve/reject actions and handles publish errors.
A complete CMS browsing/editing UI is outside this backend deliverable. API fixtures/E2E setup follow the same gate.
Downgrade removes review history and must only follow an explicit operational decision.
Legacy Prisma adoption still stamps 0001 then upgrades; `stamp head` cannot skip this migration.

## Acceptance

T-CAT-005: staff list/detail/edit, validation, draft-only and learner 403.
T-CMS-002: pending approval rejected; approve then admin publish; reject reason and resubmit;
old approval cannot authorize a new round; concurrent reviews produce one verdict.
T-CMS-001: upload/HLS cannot mutate an item outside draft.
T-NEG: learner catalog never contains internal notes/reviewer/history.
BA/CTO/Pedagogy review of this delta accompanies the PR; no new learning-domain scope.
