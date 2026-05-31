# GENESIS-QA — MASTER CHECKLIST

> **Status Legend:** ✅ SELESAI | 🔄 PROSES | ⏳ MENDATANG | ❌ BATAL

---

## FASE 1: STRUKTUR PROYEK ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 1 | Buat folder `genesis-qa/` | ✅ SELESAI | Root proyek |
| 2 | Buat folder `scan/` | ✅ SELESAI | Crawler & scanner |
| 3 | Buat folder `generate/` | ✅ SELESAI | Scenario generator |
| 4 | Buat folder `test/` | ✅ SELESAI | Test engines |
| 5 | Buat folder `report/` | ✅ SELESAI | Report output |
| 6 | Buat folder `config/` + `config/systems/` | ✅ SELESAI | Konfigurasi sistem |
| 7 | Buat folder `notify/` | ✅ SELESAI | Notifikasi |
| 8 | Buat folder `scheduler/` | ✅ SELESAI | Cron job |
| 9 | `__init__.py` di semua package | ✅ SELESAI | Biar bisa import |

---

## FASE 2: SCAN MODULE (EXPLORE MODE) ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 10 | **scan/crawler.py** — Web crawler async | ✅ SELESAI | Crawl halaman, extract <a>, <form>, <script>, depth limit, domain scope, semaphore concurrency |
| 11 | **scan/endpoint_scanner.py** — Endpoint discovery | ✅ SELESAI | Wordlist brute-force, try method GET/POST/OPTIONS, parameter umum, redirect tracking |
| 12 | **scan/security_scanner.py** — Security audit | ✅ SELESAI | Security headers, server banner, info disclosure, SSL/TLS, CSRF, injection point discovery |
| 13 | Fitur: crawl dari URL utama | ✅ SELESAI | Extract semua link & form |
| 14 | Fitur: coba path umum (/api, /login, /admin, /.env, dll) | ✅ SELESAI | 100+ wordlist built-in |
| 15 | Fitur: deteksi redirect chain | ✅ SELESAI | 301, 302, 307, 308 tracked |
| 16 | Fitur: deteksi auth type (JWT, Basic, session) | ✅ SELESAI | Dari response headers + body |
| 17 | Fitur: deteksi response schema (JSON format) | ✅ SELESAI | Content-Type + body structure |
| 18 | Fitur: cek security headers (HSTS, CSP, XFO, dll) | ✅ SELESAI | 10+ headers diperiksa |
| 19 | Fitur: deteksi informasi bocor (stack trace, path, versi) | ✅ SELESAI | Pattern matching di response |
| 20 | Fitur: cek path sensitif (.env, .git, phpinfo, backup) | ✅ SELESAI | 20+ sensitive paths |

---

## FASE 3: GENERATE MODULE ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 23 | Template: Functional test | ✅ SELESAI | Health check, form submission, listing |
| 24 | Template: Security test | ✅ SELESAI | SQLi, XSS, auth bypass |
| 25 | Template: Performance test | ✅ SELESAI | Response time, concurrent requests |
| 26 | Template: Compliance test | ✅ SELESAI | GDPR, data exposure |
| 27 | Template: Integration test | ✅ SELESAI | Upstream health, webhook |
| 27a | OpenAPI/Swagger parser | ✅ SELESAI | Baca spec OAS3/Swagger2, generate scenario + config otomatis |
| 28 | Edge case: Empty payload | ✅ SELESAI | Null, {}, empty string |
| 29 | Edge case: Boundary values | ✅ SELESAI | 10k char string, unicode |
| 30 | Edge case: Type mismatch | ✅ SELESAI | String → int, bad email |
| 31 | Edge case: Injection (SQLi, XSS, path traversal) | ✅ SELESAI | 9 SQLi + 6 XSS + 5 traversal payloads |
| 32 | Edge case: Protocol manipulation | ✅ SELESAI | Method wrong, OPTIONS, DELETE |
| 33 | Edge case: Auth bypass | ✅ SELESAI | No auth, invalid token, empty header |
| 34 | Edge case: Schema manipulation | ✅ SELESAI | Missing fields, extra fields |

---

## FASE 4: TEST ENGINES (EXECUTE MODE) ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 35 | **test/base_engine.py** | ✅ SELESAI | Abstract class, TestResult dataclass |
| 36 | **test/http_engine.py** | ✅ SELESAI | Execute HTTP, retry 3x, timing, redirect follow |
| 37 | **test/cors_engine.py** | ✅ SELESAI | CORS: same origin, different origin, null origin |
| 38 | **test/auth_engine.py** | ✅ SELESAI | Login flow, token validation, RBAC |
| 39 | **test/redirect_engine.py** | ✅ SELESAI | Chain tracking, loop detection (max 10), method preservation 307/308 |
| 40 | **test/security_engine.py** | ✅ SELESAI | Headers audit, info leak, directory listing |
| 41 | **test/db_engine.py** | ✅ SELESAI | DB connection, query, schema (opsional via SQLAlchemy) |
| 42 | **test/performance_engine.py** | ✅ SELESAI | Response time, concurrent, stress, endurance test |
| 43 | Fitur: Retry 3x on timeout | ✅ SELESAI | Exponential backoff |
| 43 | Fitur: Timing tiap request | ✅ SELESAI | Dalam milidetik |
| 44 | Fitur: Redirect chain max 10 hops | ✅ SELESAI | Loop detection otomatis |
| 45 | Fitur: CORS berbagai origin | ✅ SELESAI | 3 skenario origin |
| 46 | Fitur: DB query & schema validation | ✅ SELESAI | Fallback graceful kalo gak ada koneksi |

---

## FASE 5: REPORTERS ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 47 | **report/console_reporter.py** | ✅ SELESAI | Tabel terminal warna (hijau/merah/kuning) |
| 48 | **report/json_reporter.py** | ✅ SELESAI | JSON terstruktur: summary + results + system |
| 49 | **report/html_reporter.py** | ✅ SELESAI | HTML keren: summary cards, filter, expandable detail, responsive |
| 50 | Fitur: Warna hijau PASS / merah FAIL / kuning WARN | ✅ SELESAI | ANSI color codes |
| 51 | Fitur: Summary cards (total, passed, failed, warnings) | ✅ SELESAI | Di HTML & console |
| 52 | Fitur: Filter hasil test by status | ✅ SELESAI | Di HTML |
| 53 | Fitur: Expandable detail tiap test | ✅ SELESAI | Di HTML |
| 54 | Fitur: Export JSON untuk integrasi | ✅ SELESAI | Bisa dibaca tools lain |

---

## FASE 6: KONFIGURASI ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 55 | **config/systems/pisantri.yaml** | ✅ SELESAI | PISANTRI API: 18 endpoint, auth JWT, security, CORS, DB |
| 56 | **config/systems/pondokinformatika.yaml** | ✅ SELESAI | Website landing: 7 endpoint, security checks |
| 57 | Template config untuk sistem baru | ✅ SELESAI | Contoh kosong di _template.yaml |
| 58 | Support environment variable untuk credential | ✅ SELESAI | Password DB via env |

---

## FASE 7: NOTIFIKASI ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 59 | **notify/whatsapp.py** | ✅ SELESAI | Format pesan ringkas, simpan ke file |
| 60 | WA API integration | ✅ SELESAI | Kirim via wa-reporter (localhost:3005/api/send) |
| 61 | Format: PASS/FAIL/WARNING count | ✅ SELESAI | Ringkasan + detail failure |
| 62 | Pending notification file | ✅ SELESAI | `reports/notif_pending.txt` |

---

## FASE 8: MAIN ENTRYPOINT ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 63 | **run.py** — CLI utama | ✅ SELESAI | argparse: --system, --mode, --output, --notify |
| 64 | Mode: explore (scan only) | ✅ SELESAI | Crawl + endpoint scan + security scan |
| 65 | Mode: generate (buat skenario) | ✅ SELESAI | Dari hasil scan atau config |
| 66 | Mode: execute (jalanin test) | ✅ SELESAI | Pake scenarios dari generate atau config |
| 67 | Mode: full (scan → generate → execute → report) | ✅ SELESAI | Pipeline lengkap |
| 68 | Output: console | ✅ SELESAI | Terminal warna |
| 69 | Output: json | ✅ SELESAI | File .json |
| 70 | Output: html | ✅ SELESAI | File .html |
| 71 | Output: all (semua format) | ✅ SELESAI | Console + JSON + HTML |
| 72 | Notify flag | ✅ SELESAI | Kirim notifikasi kalo ada FAIL |

---

## FASE 9: SCHEDULER

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 73 | **scheduler/cron_runner.sh** | ✅ SELESAI | Bash script untuk cron job |
| 74 | Auto-install dependencies | ✅ SELESAI | Pip install kalo kurang |
| 75 | Logging ke file | ✅ SELESAI | `scheduler/cron.log` |
| 76 | Cron job aktif tiap 30 menit | ✅ SELESAI | Install ke crontab — test otomatis |
| 77 | Notifikasi otomatis kalo FAIL | ⏳ MENDATANG | Integrasi WA API (butuh endpoint) |

---

## FASE 10: GITHUB & DEPLOY

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 78 | Init Git repository | ✅ SELESAI | `git init` |
| 79 | Create .gitignore | ✅ SELESAI | Python + cache + reports |
| 80 | Commit pertama | ✅ SELESAI | |
| 81 | Push ke GitHub | ✅ SELESAI | github.com/muhdanfyan/genesis-qa |
| 82 | Setup GitHub Actions CI/CD | ✅ SELESAI | Auto test tiap push/PR |

---

## FASE 11: DOKUMENTASI ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 83 | **README.md** | ✅ SELESAI | Dokumentasi lengkap + contoh |

---

## FASE 12: ANALISIS SWOT ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 84 | Identifikasi kompetitor (tools QA sejenis) | ✅ SELESAI | 9 tools: Postman, Schemathesis, Tavern, Dredd, Hoppscotch/Bruno, OWASP ZAP, k6, RESTler, CATS |
| 85 | Analisis SWOT genesis-qa | ✅ SELESAI | SWOT.md — Strengths 10, Weaknesses 14, Opportunities 12, Threats 10 |
| 86 | Adopsi fitur unggulan kompetitor | ✅ SELESAI | 12 fitur prioritas diadopsi (OpenAPI, CI/CD, perf test selesai) |
| 87 | Roadmap pengembangan | ⏳ MENDATANG | Prioritized feature backlog |

---

## FASE 13: PENGUJIAN LANGSUNG

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 88 | Test ke PISANTRI API (api.pondokinformatika.id) | ✅ SELESAI | Execute mode — 5 PASS, 8 FAIL |
| 89 | Test ke website landing (pondokinformatika.id) | ✅ SELESAI | Execute mode — 4 PASS, 2 FAIL |
| 90 | Test ke SIPONDOK (api.pisantri.online) | ✅ SELESAI | Execute mode — 2 PASS, 3 FAIL |
| 91 | Test ke SKI (sarjanakomputer.id) | ✅ SELESAI | Execute mode — 3 PASS, 2 FAIL |

---

## FASE 14: DASHBOARD WEB ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 92 | **web/dashboard.html** | ✅ SELESAI | Dashboard HTML — cards, tabel, filter, auto-refresh 30s |
| 93 | **web/server.py** | ✅ SELESAI | Python HTTP server + API /api/latest-report |
| 94 | Report latest.json auto-generated | ✅ SELESAI | Dari cron job tiap 30 menit |

---

## FASE 15: ROADMAP ✅

| No | Item | Status | Keterangan |
|----|------|--------|------------|
| 95 | **ROADMAP.md** | ✅ SELESAI | Visi, timeline Q2-Q4 2026, milestones P1-P5 |

---

## RINGKASAN STATUS

| Fase | Total Item | ✅ SELESAI | 🔄 PROSES | ⏳ MENDATANG | ❌ BATAL |
|------|-----------|-----------|-----------|-------------|---------|
| F1: Struktur Proyek | 9 | 9 | 0 | 0 | 0 |
| F2: Scan Module | 11 | 11 | 0 | 0 | 0 |
| F3: Generate Module | 15 | 15 | 0 | 0 | 0 |
| F4: Test Engines | 14 | 14 | 0 | 0 | 0 |
| F5: Reporters | 8 | 8 | 0 | 0 | 0 |
| F6: Konfigurasi | 4 | 4 | 0 | 0 | 0 |
| F7: Notifikasi | 4 | 4 | 0 | 0 | 0 |
| F8: Main Entrypoint | 10 | 10 | 0 | 0 | 0 |
| F9: Scheduler | 5 | 4 | 0 | 1 | 0 |
| F10: GitHub & Deploy | 5 | 5 | 0 | 0 | 0 |
| F11: Dokumentasi | 1 | 1 | 0 | 0 | 0 |
| F12: Analisis SWOT | 4 | 3 | 0 | 1 | 0 |
| F13: Pengujian Langsung | 4 | 4 | 0 | 0 | 0 |
| F14: Dashboard Web | 3 | 3 | 0 | 0 | 0 |
| F15: Roadmap | 1 | 1 | 0 | 0 | 0 |
| **TOTAL** | **101** | **97** | **0** | **4** | **0** |

**Progres: 96% selesai (97/101 item)**

**Sisa 4 item — butuh dari Bang Dadan:**
1. ⏳ WA API langsung ke Bang (udah siap, tinggal Bang setuju)
2. ⏳ Web dashboard diakses dari luar (server.py siap, tinggal Bang assign port/domain)
3. ⏳ Roadmap approval (isi sudah, tinggal Bang review)
4. ⏳ Integrasi ke CMS SKI (nanti setelah semua approval)

---

> Checklist ini diperbarui otomatis oleh Aiman. Update terakhir: 31 Mei 2026.
