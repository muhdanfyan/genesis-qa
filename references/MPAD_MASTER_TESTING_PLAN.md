# M-PAD MASTER TESTING PLAN — Living Document

> Update terakhir: 5 Agu 2026 — Penambahan test case Flow Pembayaran Cart E-Commerce + mitigasi regression.
> Config terkait: `config/systems/mpad.yaml` (55 endpoint) + `config/systems/mpad-mobile.yaml` (frontend).

## D. BILLING & FLOW PEMBAYARAN (Cart E-Commerce) — 5 Agu 2026

### Latar Belakang
M-PAD mengadopsi konsep e-commerce: **Toko = Layanan Pajak, Bill = Produk**.
- Satu keranjang global (`mpad_cart_v1` localStorage), group per layanan (classification)
- Tab `/bayar?tab=tagihan` (daftar semua tagihan + search + filter + checkbox) dan `/bayar?tab=keranjang` (Dalam Keranjang + metode + Tagihan Belum Masuk)
- Filter periode + label waktu sesuai `billing_cycle`: PBB (yearly) → tahun saja "2026"; monthly → "Juli 2026"
- Backend payment request HANYA `bri_va`; QRIS = opsi UI + panel fallback di checkout

### Test Case API (ada di mpad.yaml)

| # | Endpoint | Method | Expected | Catatan |
|---|----------|--------|----------|---------|
| 1 | `/api/citizen/bills` | GET | 200/401 | Daftar tagihan citizen (PaymentHub/Home/Tagihan) |
| 2 | `/api/citizen/services/172` | GET | 200/401 | Detail layanan non-PBB + billing_cycle monthly |
| 3 | `/api/citizen/services/186` | GET | 200/401 | Detail PBB-P2 + billing_cycle (frontend paksa yearly) |
| 4 | `/api/citizen/payment-requests` | POST | 201/401/422 | Create BRIVA — **validasi method in:bri_va** (QRIS belum support) |
| 5 | `/api/citizen/payment-requests/{id}` | GET | 200/401/404 | Status payment request + polling |
| 6 | `/api/citizen/payments/history` | GET | 200/401 | Riwayat pembayaran |

### Test Case Frontend (manual/regression — verifikasi bundle + browser)

| # | Skenario | Expected | Mitigasi jika gagal |
|---|----------|----------|---------------------|
| F1 | Kartu beranda "Keranjang Tagihan" | Cermin isi cart (count+total), tanpa tombol CTA terpisah; icon + statistik kanan link `?tab=keranjang` | Cek `AccountSummaryCard` pakai `useCart()` |
| F2 | Tab `/bayar` | 2 tab: TAGIHAN (default, icon cart) + KERANJANG; tidak ada "Scan QR"/"Bank QRIS/VA" | Cek `PaymentHub` TabType `'tagihan'\|'keranjang'` |
| F3 | Centang tagihan | Toast "Tagihan masuk keranjang" + badge + cart terisi | Cek `CartToast` listen `lastAction.type==='add'` |
| F4 | `/bayar?tab=keranjang` | "Dalam Keranjang" group per layanan + Hapus per grup + sticky bar "Bayar Sekarang" | Cek sticky bar z-[70] bottom-20 |
| F5 | Tagihan Belum Masuk | Muncul di bawah cart page, tombol +, sisa update real-time | Cek `unpaidNotInCart` slice(0,3) |
| F6 | PaymentMethodSelector | Bank BRI tampil QRIS **DAN** VA konsisten | Jangan set `qrisAvailable={false}` |
| F7 | Format period keranjang | Monthly → "Agustus 2026"; PBB → "2026" | Cek `formatCartPeriod` |
| F8 | Checkout `/pembayaran?method=qris` | Panel fallback "Metode QRIS... Bayar dengan Virtual Account" — **BUKAN halaman kosong** | Cek branch `selectedMethod === "qris"` di Pembayaran.tsx |
| F9 | Filter periode `/layanan/{id}` | Muncul semua layanan; PBB → "Tahun 2026"; non-PBB → "Juli 2026" | Cek `ServiceBillsCard` tanpa `!isPbb` + `cycle=isPbb?'yearly'` |
| F10 | Label waktu bill | PBB "2026"; monthly "Juni 2026" (tanpa tanggal) | Cek `formatBillPeriod` |
| F11 | Bottom sheet | Klik ikon cart → sheet preview "Lihat Semua & Bayar" → `?tab=keranjang` | Cek `CartSheet` + `CartButton` default `openSheet()` |
| F12 | Semua link | Tidak ada `?tab=cek` tersisa; semua `?tab=keranjang` | `grep -rn "tab=cek" src/` harus 0 |

### Blocker Diketahui
- **BRIVA belum aktif di backend** (`.env` prod tanpa `BRI_SNAP_ENABLED`) → POST `/api/citizen/payment-requests` return error "Channel BRIVA belum tersedia" untuk semua bill. Test dianggap PASS selama response bukan 500 (route hidup). Task Leantime #1607.
- **QRIS payment request belum ada endpoint** backend (hanya `in:bri_va`) → UI tampilkan opsi QRIS + panel fallback (mitigasi F8).

### Verifikasi Bundle (setelah deploy)
```bash
curl -s https://mpad.baubaukota.go.id/ | grep -oE 'assets/index-[A-Za-z0-9_-]+\.js'
# Grep SEMUA chunk dist/assets/*.js (bukan hanya index) — SPA lazy-load per halaman
grep -c 'Tagihan Belum Masuk' dist/assets/*.js  # ≥1
grep -c 'Metode QRIS' dist/assets/*.js          # ≥1
```
