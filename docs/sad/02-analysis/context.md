# System context

```
                    ┌─────────────┐
                    │   Learner   │
                    │ (test acct) │
                    └──────┬──────┘
                           │ HTTPS
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐
      │  Web    │    │  Mobile   │   │   iPad    │
      │ Next.js │    │ Expo app  │   │ same app  │
      └────┬────┘    └─────┬─────┘   └─────┬─────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │ Platform    │
                    │ API + DB    │
                    └──────┬──────┘
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
       │    CMS     │ │  Media  │ │ Analytics │
       │ (teachers) │ │ store   │ │ events    │
       └──────▲─────┘ └─────────┘ └───────────┘
              │
       ┌──────┴──────┐
       │ Teacher /   │
       │ Level QA    │
       └─────────────┘
```

Hệ thống bên ngoài Q1: email (magic không bắt buộc), object storage, (sau này) transcode. Không thanh toán, không IdP xã hội bắt buộc v1.
