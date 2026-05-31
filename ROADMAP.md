# Genesis-QA Roadmap

**Visi:** Menjadi tools QA 全能 (serba bisa) untuk semua sistem milik Bang Dadan — satu titik kendali kualitas yang terintegrasi, otomatis, dan cerdas.

---

## Timeline

| Periode | Fokus |
|---------|-------|
| **Q2 2026** (Sekarang) | Foundation & Core Engine |
| **Q3 2026** | Integrasi & Ekspansi |
| **Q4 2026** | Intelligence & Orchestration |

---

## Q2 2026 — Foundation & Core Engine

Prioritas utama: membangun fondasi agar QA berjalan otomatis dari pipeline CI/CD.

### P1 — OpenAPI Parser ✅ (Selesai)
- Parse spec OpenAPI 3.0 / 3.1 (JSON & YAML)
- Generate test case skeleton per endpoint
- Validasi skema response (required fields, tipe data)

### P1 — CI/CD Pipeline ✅ (Selesai)
- Integrasi GitHub Actions / self-hosted runner
- Auto-trigger test tiap push ke branch utama
- Report artifact (.json) tersimpan per commit
- Notifikasi ke WhatsApp (via API nanti)

### P2 — Performance Engine ✅ (Selesai)
- Stress test endpoint dengan kustom concurrency
- Ukur response time (avg, p50, p95, p99)
- Threshold alert: jika response time > 2s

### P2 — Cron Job ✅ (Selesai)
- Jadwalkan test rutin (setiap jam / setiap 6 jam / setiap hari)
- Jalankan di background via systemd timer
- Kirim notifikasi jika ada regresi

---

## Q3 2026 — Integrasi & Ekspansi

Memperluas jangkauan ke sistem eksternal dan real-time monitoring.

### P3 — WA API Integration ⚡
- Kirim laporan test harian ke grup WhatsApp Bang Dadan
- Format: ringkasan eksekutif (total, pass, fail, warn)
- Command: `/qa-test` trigger test manual via WA
- Command: `/qa-report` minta laporan terakhir

### P3 — Webhook Alerts ⚡
- Kirim webhook ke Discord / Slack / Telegram
- Custom payload per target (embed, message, dll)
- Retry logic (3x, exponential backoff)
- Hanya untuk event penting: FAIL, timeout, error parsing

### P4 — GUI Dashboard 📋
- Single-file HTML dashboard (bisa jalan di browser manapun)
- Summary cards: Total, PASS, FAIL, WARN
- Filter hasil test by status
- Auto-refresh setiap 30 detik
- Tabel detail: endpoint, status, response time, timestamp
- Responsive untuk mobile

### P4 — Multi-system Orchestrator 📋
- Daftar sistem: siakad, ewallet, elearning, dll.
- Test semua sistem secara paralel
- Report aggregate (gabungan semua sistem)

---

## Q4 2026 — Intelligence & Orchestration

Memanfaatkan AI untuk deteksi dini dan prediksi.

### P5 — AI-powered Test Generation 🔮
- Analisis changelog / diff commit
- Generate test case baru otomatis berdasarkan perubahan kode
- Rekomendasi prioritas test: mana yang paling mungkin broken
- Integrasi dengan LLM lokal (via Ollama / vLLM)

### P5 — Anomaly Detection 🔮
- Deteksi pola anomali pada response time
- Bandingkan dengan historical data (7 hari terakhir)
- Alert otomatis jika ada spike di luar threshold dinamis
- Learning mode: threshold menyesuaikan dengan traffic normal

---

## Matriks Prioritas (SWOT Adoption Plan)

| Priority | Area | Status |
|----------|------|--------|
| P1 | OpenAPI Parser, CI/CD Pipeline | ✅ Done |
| P2 | Performance Engine, Cron Job | ✅ Done |
| P3 | WA API Integration, Webhook Alerts | ⚡ In Progress |
| P4 | GUI Dashboard, Multi-system Orchestrator | 📋 Planned |
| P5 | AI-powered Test Generation, Anomaly Detection | 🔮 Future |

---

## Struktur Direktori Target

```
genesis-qa/
├── ROADMAP.md
├── web/
│   ├── dashboard.html
│   └── server.py
├── reports/
│   └── latest.json
├── parsers/
│   ├── openapi_parser.py
│   └── ...
├── engines/
│   ├── performance.py
│   └── ...
├── cron/
│   └── scheduler.py
├── integrations/
│   ├── wa_api.py
│   └── webhook.py
└── config/
    └── systems.yaml
```
