# Ukuran Beranda: University of Edinburgh vs EduAI

Beranda EduAI memakai struktur lebar penuh. Ukurannya diambil dari https://local.ed.ac.uk/, sedangkan warna (navy/emas), font (Public Sans, Libre Baskerville), logo, teks, dan foto tetap milik EduAI.

**Cara mengukur:** halaman dibuka di Chrome lewat Playwright pada 5 November 2026, lalu diukur dengan `getBoundingClientRect` dan `getComputedStyle`. Semua angka dalam piksel CSS. EduAI diukur dengan cara yang sama setelah perubahan.

## Yang ada di local.ed.ac.uk

Urutan di situs itu dari atas: **header putih** (lambang dan nama), lalu **pita judul berwarna** ("EDINBURGH LOCAL"), lalu **menu putih**, lalu isi. Ada dua hal yang **tidak ada** di beranda situs itu:

- **Bilah menu gelap di paling atas.** Menu Edinburgh berwarna putih dan terletak di bawah pita judul. EduAI memakai ukuran menu Edinburgh (tinggi 59,4 px, huruf 17,6 px), tetapi menaruhnya di atas dengan latar navy sesuai permintaan.
- **Banner foto.** Banner EduAI adalah kolase webcam tim EduAI (`banner_indikasi.webp`, 4120 × 760 px). Tingginya mengikuti rasio gambar (lebar layar × 760 / 4120) agar tidak ada foto yang terpotong.

## Tabel ukuran (Edinburgh / EduAI)

| Ukuran | 1280 px | 1440 px | 390 px |
|---|---|---|---|
| Tinggi bilah menu | 117,8 (menu terlipat 2 baris) / 59,4 | 59,4 / 59,4 | 38 (tombol Menu) / 44 |
| Font menu | 17,6 / 17,6 | 17,6 / 17,6 | 17,6 / 17,6 |
| Jarak antartautan menu | 32 (padding 16 + 16) / 32 | 32 / 32 | – |
| Tinggi header | 119 / 119 | 119 / 119 | 121,5 / 123 |
| Padding atas-bawah header | 20 / 20 | 20 / 20 | 5 / 5 |
| Tinggi lambang di header | 79 / 79 | 79 / 79 | 78,1 / 56 |
| Font tautan kanan header | 17,66 / 17,66 | 18,03 / 18,03 | 15,60 / 15,60 |
| Tinggi tombol di kanan header (Edinburgh: kotak cari) | 44,3 / 45 | 45,2 / 45 | – / 45 |
| Tinggi banner foto | tidak ada / 236,1 | tidak ada / 265,6 | tidak ada / 71,9 |
| Tinggi pita judul | 109 / 185,9 | 117 / 195 | 64,5 / 182,7 |
| Jarak atas pita ke judul | 34,2 / 34,2 | 36,5 / 36,5 | 21,1 / 21,4 |
| Font judul pita (huruf besar, serif) | 38,26 / 38,26 | 40,98 / 40,98 | 23,13 / 23,13 |
| Padding kiri-kanan | 32 / 32 | 32 / 32 | 16 / 16 |
| Lebar latar bilah | penuh / penuh | penuh / penuh | penuh / penuh |

**Pita judul EduAI lebih tinggi** karena berisi kalimat visi dan tautan "Baca pendekatan kami", sedangkan pita Edinburgh hanya berisi judul. Jarak dari tepi atas pita ke judul dan ukuran font judulnya sama.

**Nama "EduAI Ujian" di header (32 px; 24 px di HP)** memakai angka perkiraan pemilik proyek. Di Edinburgh, nama situs merupakan bagian dari gambar logo, jadi ukuran fontnya tidak bisa diukur.

**Bilah menu di HP setinggi 44 px** (Edinburgh 38 px) agar tombol cukup besar untuk disentuh jari.

## Lebar maksimum

Isi setiap bilah dibatasi paling lebar 1440 px dan ditaruh di tengah, tetapi latarnya tetap selebar layar. Di 1920 px isi mulai dari x = 240. Edinburgh memakai batas 1564 px untuk headernya.

## Rumus yang dipakai

Ukuran Edinburgh ikut lebar layar. Rumus ini diturunkan dari hasil ukur di 1280 dan 1440 px, dan cocok juga untuk 390, 1024, 1366, dan 1920 px. Semuanya ada di `frontend/src/index.css` (kelas `.bd-*`).

| Kelas | Rumus |
|---|---|
| `.bd-band` | maks 1440 px, padding 16 px (< 576 px) atau 32 px |
| `.bd-text` | `min(14,7px + 0,23125vw, 18,4px)`, tinggi baris 1,5 |
| `.bd-h1` (judul pita) | `min(16,5px + 1,7vw, 42px)` |
| `.bd-h2` (judul kartu) | `min(21,4px + 0,65vw, 31,8px)` |
| `.bd-title-top` / `.bd-title-bottom` | `min(15,8px + 1,437vw, 37,4px)` / `min(11,1px + 1,6875vw, 36,4px)` |
| `.bd-card-title` / `.bd-card-text` | 18 px / 12 px |

## Kartu foto dan "Yang diperhatikan AI"

Kedua bagian memakai container yang sama: isi paling lebar 960 px di tengah (`.bd-band.bd-narrow`), dengan padding 32 px (16 px di HP). Gridnya 3 kolom dengan jarak 20 px mulai 768 px, dan 1 kolom di bawahnya, sehingga kolom kedua bagian sejajar. Foto kartu 16:9, judul kartu 18 px serif, deskripsi 12 px.

| Ukuran | 1024 px | 1280 px | 1440 px | 390 px |
|---|---|---|---|---|
| Lebar container kartu foto | 960 | 960 | 960 | 358 |
| Lebar container "Yang diperhatikan AI" | 960 | 960 | 960 | 358 |
| Tepi kiri (x) | 32 | 160 | 240 | 16 |
| Lebar kartu | 306,7 | 306,7 | 306,7 | 358 |
| Foto kartu | 306,7 × 172,5 | 306,7 × 172,5 | 306,7 × 172,5 | 358 × 201,4 |
