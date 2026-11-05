# Protokol Evaluasi Indikasi EduAI

> **Status: USULAN. Perlu persetujuan pihak sekolah dan komite etik sebelum pilot dimulai.**
> Tidak ada perekaman relawan yang boleh dilakukan sebelum kedua persetujuan itu tertulis.

| | |
|---|---|
| Versi dokumen | 0.1 (usulan), 2 November 2026 |
| Konfigurasi yang dievaluasi | `ai/eduai-ai/config.yaml`, `version: 0.2-provisional` |
| Alat yang ada | `ai/eduai-ai/scripts/run_webcam.py`, `ai/eduai-ai/scripts/evaluate.py` |

---

## 1. Tujuan dan pertanyaan evaluasi

EduAI tidak memutuskan apakah siswa curang. EduAI menandai **indikasi** yang kemudian ditinjau pengawas. Karena itu, pertanyaannya bukan "apakah sistem mendeteksi kecurangan", melainkan:

> **Apakah setiap indikasi cukup andal untuk membantu pengawas, tanpa membebaninya dengan tanda palsu dan tanpa membuat siswa dicurigai tanpa alasan?**

Dua ukuran utama per indikasi:

| Ukuran | Arti bagi pengawas dan siswa |
|---|---|
| **False positive per jam (FP/jam) per siswa** | Berapa kali dalam satu jam ujian seorang siswa yang berperilaku wajar ditandai. Ini ukuran beban dan risiko utama. |
| **Recall** | Dari kejadian yang memang terjadi, berapa bagian yang ditandai. |

Precision dilaporkan sebagai pelengkap. Precision sangat bergantung pada seberapa sering perilaku itu muncul dalam pilot, sehingga tidak bisa dipindahkan begitu saja ke ujian sungguhan.

Indikasi yang dievaluasi, beserta aturannya saat ini (semua ambang **sementara**):

| Indikasi | Aturan sekarang | Model di baliknya |
|---|---|---|
| `FACE_ABSENT` | tidak ada wajah ≥5 detik | BlazeFace short-range |
| `HEAD_TURN` | kepala berbelok ≥30° dari posisi normal siswa, ≥3 detik (posisi normal dipelajari 45 detik pertama) | Face Landmarker |
| `HEAD_TURN_REPEATED` | 5 kali menoleh (masing-masing ≥1 detik) dalam 120 detik | Face Landmarker |
| `PHONE_VISIBLE` | objek "cell phone" dengan skor ≥0,5 selama 1,5 detik | EfficientDet-Lite0 (COCO) |
| `MULTIPLE_PERSONS` | ≥2 wajah atau ≥2 "person" selama 2 detik | BlazeFace + EfficientDet-Lite0 |
| `OTHER_VOICE` | skor suara bicara ≥0,30 di browser, sementara mulut siswa diam, ≥2 detik | YAMNet (browser) + blendshape `jawOpen` |
| `CANNOT_ANALYZE` | gelap, buram, beku, atau resolusi terlalu kecil ≥2 detik | aturan kualitas citra, tanpa model |

`HEAD_TURN_REPEATED` ikut dievaluasi karena turunan langsung dari `HEAD_TURN`.

`CANNOT_ANALYZE` diperlakukan berbeda. Ini **status kualitas video, bukan indikasi perilaku**, sehingga pertanyaannya adalah apakah sistem jujur mengatakan "tidak dapat dianalisis" ketika memang tidak bisa, dan tidak mengatakannya ketika video sebenarnya layak.

---

## 2. Skenario pilot

### 2.1 Bentuk sesi

Setiap relawan menjalani dua jenis sesi, di perangkat dan ruangan yang mirip dengan ujian sungguhan:

1. **Sesi wajar (30–45 menit):** mengerjakan soal latihan sungguhan tanpa instruksi perilaku. Sesi ini menjadi sumber utama FP/jam.
2. **Sesi skenario (sekitar 20 menit):** relawan mengikuti kartu instruksi berurutan, berisi perilaku yang dicari dan perilaku wajar yang mirip ("jebakan"). Waktu tiap instruksi dicatat oleh operator, tetapi label akhir tetap dibuat pelabel dari video (bagian 3).

Kartu instruksi diacak urutannya per relawan, supaya sistem tidak "belajar" dari urutan yang sama.

### 2.2 Skenario per indikasi

| Indikasi | Perilaku yang dicari (positif) | Perilaku wajar yang mirip (harus tidak ditandai) |
|---|---|---|
| `FACE_ABSENT` | keluar dari bingkai 5–15 detik; menutup kamera dengan tangan | menunduk menulis (wajah sebagian terlihat); bersandar ke belakang; keluar bingkai <5 detik (mengambil pensil) |
| `HEAD_TURN` | menoleh ke kiri, kanan, atau atas >30° selama 3–10 detik | melihat keyboard atau kertas; melirik jam <3 detik; meregangkan leher; membaca soal di layar besar sambil sedikit menoleh |
| `HEAD_TURN_REPEATED` | 5–7 kali menoleh dalam 2 menit | 2–3 kali menoleh dalam 2 menit; menoleh sesekali sepanjang sesi |
| `PHONE_VISIBLE` | memegang ponsel di depan kamera; ponsel di meja terlihat; mengetik di ponsel | kalkulator, remote, dompet, power bank, kotak pensil gelap; ponsel di saku (tidak terlihat) |
| `MULTIPLE_PERSONS` | orang kedua masuk di belakang; orang kedua duduk di samping | poster atau foto berwajah di dinding; pantulan di cermin atau jendela; boneka atau gambar wajah di sampul buku |
| `OTHER_VOICE` | orang lain berbicara di luar bingkai saat siswa diam; orang lain berbisik | siswa membaca soal pelan-pelan; TV atau radio tetangga; suara kendaraan; batuk; siswa diam di ruangan sunyi |
| `CANNOT_ANALYZE` | lampu dimatikan; lensa ditutup; cahaya kuat dari belakang (backlight); koneksi diputus sehingga gambar beku | ruangan redup tetapi wajah masih terlihat; siswa duduk sangat diam (bukan beku) |

**Kondisi perilaku wajar yang wajib ada di sesi wajar:** menunduk membaca, menulis di kertas, memakai kacamata (termasuk kacamata yang memantulkan cahaya layar), dan ruangan redup. Kondisi ini paling mungkin memicu tanda palsu, dan saat ini belum pernah diuji.

### 2.3 Jumlah minimum dan alasannya

| Ukuran | Minimum yang diusulkan | Alasan |
|---|---|---|
| Relawan | **≥24 orang berbeda** | Cukup untuk dibagi dua (12 kalibrasi, 12 uji) **per orang**, dan cukup untuk melihat perbedaan kasar antarkondisi (kacamata atau tidak, kamera bawaan atau eksternal). Tidak cukup untuk kesimpulan bias yang kuat (lihat 5.3). |
| Jam sesi wajar di **set uji** | **≥10 jam** total (sekitar 12 relawan × 50 menit) | Bila tidak ada satu pun tanda palsu dalam *T* jam, batas atas 95% FP/jam adalah sekitar 3/*T*. Dengan 10 jam, batas atasnya ±0,3 per jam. Dengan hanya 1 jam, batas atasnya 3 per jam, yang tidak informatif. |
| Kejadian positif berlabel per indikasi di **set uji** | **≥30** | Dengan 30 kejadian dan recall teramati 0,80, interval Wilson 95% kira-kira 0,63–0,90. Di bawah sekitar 20 kejadian, intervalnya terlalu lebar untuk membedakan sistem yang baik dari yang buruk. |
| Kejadian positif per indikasi di **set kalibrasi** | **≥30** | Agar penyetelan ambang tidak bergantung pada beberapa kejadian saja. |
| Pengulangan per relawan per skenario | 2–3 kali | Supaya 30 kejadian tidak berasal dari satu atau dua orang saja. |

Angka ini batas bawah. Bila anggaran waktu memungkinkan, menambah **jumlah orang** lebih berharga daripada menambah durasi per orang, karena variasi antarorang (wajah, kamera, ruangan) adalah sumber kesalahan terbesar.

`OTHER_VOICE` hanya bisa diuji pada relawan yang memberi persetujuan audio terpisah dan pada mode frame browser. Jam paparannya dihitung terpisah (bagian 5.1).

---

## 3. Prosedur pelabelan

1. **Pedoman tertulis lebih dulu.** Setiap indikasi didefinisikan secara operasional sebelum pelabelan, misalnya: "`HEAD_TURN` dimulai saat hidung jelas melewati tepi bahu dan berakhir saat kembali menghadap layar". Pedoman ini diuji coba pada 2 video, lalu dibekukan.
2. **Dua pelabel independen.** Dua orang melabeli setiap video tanpa melihat keluaran sistem dan tanpa saling berdiskusi. Setiap label memuat: video, indikasi, waktu mulai, waktu akhir, dan catatan kondisi.
3. **Kesepakatan antarpelabel (Cohen's kappa).** Video dipotong menjadi segmen 1 detik. Untuk tiap indikasi, setiap segmen diberi nilai "ada" atau "tidak ada" oleh masing-masing pelabel, lalu kappa dihitung per indikasi.
   - **Target κ ≥ 0,70.**
   - Bila κ < 0,70, pedoman diperbaiki, lalu video dilabeli ulang. Evaluasi tidak dilanjutkan dengan label yang lemah.
   - Kappa dilaporkan di publikasi untuk setiap indikasi.
4. **Penyelesaian beda label.**
   - Selisih batas waktu ≤1 detik: pakai rata-rata waktu kedua pelabel.
   - Satu pelabel menandai dan yang lain tidak, atau selisih batas waktu >1 detik: pelabel ketiga (adjudikator) memutuskan dengan melihat video, juga tanpa melihat keluaran sistem.
   - Jumlah kasus yang diselesaikan adjudikator dicatat per indikasi.
5. **Label akhir dibekukan sebelum keluaran sistem dibuka**, dan disimpan dengan hash berkas.

---

## 4. Pemisahan data

- **Pemisahan per orang, bukan per video atau per potongan.** Seorang relawan hanya boleh berada di satu set. Wajah, kamera, dan ruangan yang sama di kedua set akan membuat hasil uji terlalu optimis.
- **Set kalibrasi (sekitar 50% relawan):** dipakai untuk menyetel ambang di `config.yaml` sebanyak yang diperlukan.
- **Set uji (sekitar 50% relawan):** tidak dibuka sama sekali selama kalibrasi.
- **Pembekuan:** sebelum set uji dibuka, `config.yaml` diberi versi baru (misalnya `0.3-calibrated`) dan hash berkasnya dicatat. Set uji dijalankan **satu kali** dengan versi itu.
- **Bila ambang diubah setelah set uji dibuka,** hasil uji itu tidak lagi independen. Hasilnya harus dilaporkan sebagai hasil kalibrasi, dan perlu set uji baru dari relawan baru.
- Pembagian relawan ke kedua set dilakukan secara acak, dengan menjaga proporsi kondisi utama (kacamata, jenis kamera) kira-kira seimbang.

---

## 5. Metrik

### 5.1 Per indikasi

| Metrik | Cara hitung | Interval kepercayaan 95% |
|---|---|---|
| Recall | TP / (TP + FN) | Wilson |
| Precision | TP / (TP + FP) | Wilson |
| **FP/jam per siswa** | FP / jam paparan | Poisson eksak (Garwood). Wilson tidak tepat untuk laju. |
| Waktu sampai tanda | selisih antara awal label dan awal tanda sistem | median dan rentang antarkuartil |

**Pencocokan kejadian.** Satu tanda sistem cocok dengan satu label bila indikasinya sama dan rentang waktunya beririsan, dengan toleransi ±2 detik di awal. Satu label hanya boleh dicocokkan satu kali. Tanda tambahan untuk kejadian yang sama dihitung sebagai FP dan dilaporkan terpisah sebagai "tanda ganda".

**Jam paparan** dihitung per indikasi, hanya selama indikasi itu memang bisa muncul:
- `HEAD_TURN`: setelah 45 detik pembentukan posisi normal.
- `OTHER_VOICE`: hanya saat persetujuan audio aktif dan mode frame browser dipakai.
- Semua indikasi: tidak termasuk periode yang sistem sendiri nyatakan `CANNOT_ANALYZE`. Periode ini dilaporkan terpisah.

**Untuk `CANNOT_ANALYZE`:** recall (video yang memang tidak layak dianalisis ditandai) dan FP/jam (video yang layak dinyatakan tidak layak). Hasilnya dilaporkan terpisah dari indikasi perilaku.

### 5.2 Kriteria penerimaan

Angka berikut **usulan yang harus disepakati dengan sekolah sebelum set uji dibuka**, bukan setelahnya:

- Batas atas 95% FP/jam per siswa ≤ 0,5 untuk setiap indikasi. Dalam ujian 90 menit dengan 30 siswa, itu berarti paling banyak sekitar 22 tanda palsu yang perlu ditinjau pengawas.
- Batas bawah 95% recall ≥ 0,60.
- Indikasi yang tidak memenuhi kriteria dinonaktifkan atau diberi label "eksperimental" di antarmuka. Indikasi itu tidak dipakai sampai diperbaiki dan diuji ulang.

### 5.3 Analisis per kondisi (bias)

Metrik di 5.1 dihitung ulang per kelompok:

| Faktor | Kelompok |
|---|---|
| Pencahayaan | terang, sedang, redup (diukur dengan lux meter atau kecerahan rata-rata frame) |
| Kacamata | tanpa, kacamata biasa, kacamata yang memantulkan layar |
| Jenis kamera | kamera bawaan laptop, webcam USB, kamera ponsel; dan resolusinya |
| Sudut kamera | sejajar mata, dari bawah (laptop di meja), dari samping |
| Warna kulit | skala Monk Skin Tone (10 tingkat), dikelompokkan menjadi 3 kelompok untuk analisis |
| Hijab atau penutup kepala, rambut menutupi wajah | ya, tidak |

**Batasan yang harus diungkap.** Dengan sekitar 24 relawan, setiap kelompok hanya berisi beberapa orang. Analisis ini bersifat **eksploratif**, untuk menemukan pola yang perlu diselidiki, bukan untuk menyatakan bahwa sistem "tidak bias". Interval kepercayaan per kelompok harus selalu ditampilkan.

**Data sensitif.** Warna kulit dan penutup kepala adalah data sensitif. Data ini dicatat hanya bila relawan setuju secara khusus. Pencatatan dilakukan oleh pelabel menurut skala yang sama, atau dilaporkan sendiri oleh relawan. Data ini disimpan terpisah dari identitas.

---

## 6. Etika dan data

### 6.1 Persetujuan dan izin

- **Izin komite etik penelitian** (misalnya KEPK institusi atau universitas mitra) **wajib sebelum perekaman pertama.** Pilot ini merekam wajah dan, bila disetujui, audio. Wajah termasuk data biometrik, yang dalam UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi digolongkan sebagai data pribadi yang bersifat spesifik.
- **Persetujuan tertulis relawan**, dengan penjelasan dalam bahasa sederhana: apa yang direkam, untuk apa, berapa lama disimpan, siapa yang melihat, dan hak untuk mundur kapan saja tanpa konsekuensi.
- **Siswa di bawah 18 tahun** (sebagian besar siswa SMA): **persetujuan orang tua atau wali dan persetujuan siswa itu sendiri.** Keduanya diperlukan.
- **Persetujuan bertingkat** dengan kotak centang terpisah untuk:
  - rekaman video;
  - rekaman audio (untuk `OTHER_VOICE`);
  - pencatatan warna kulit dan penutup kepala;
  - pemakaian cuplikan wajah di publikasi (default: tidak).
- **Kesukarelaan.** Pilot tidak boleh menjadi syarat nilai. Ikut atau tidak ikut tidak memengaruhi siswa. Rekaman pilot tidak boleh dipakai untuk penilaian atau tindakan disiplin apa pun.
- Pelaksanaan pilot juga perlu disetujui pimpinan sekolah. Untuk penerapan sesudahnya, disarankan penilaian dampak pelindungan data pribadi (DPIA).

### 6.2 Anonimisasi

- Setiap relawan diberi **kode samaran** (misalnya `R07`). Daftar kode ke nama disimpan terpisah dan terenkripsi, hanya oleh penanggung jawab penelitian.
- Video tidak dapat dianonimkan sepenuhnya, karena evaluasi membutuhkan wajah. Karena itu, akses dibatasi (6.4).
- Nama berkas, label, dan hasil hanya memakai kode samaran. Metadata kamera (nama perangkat, lokasi GPS) dihapus.
- Publikasi hanya memuat angka agregat. Cuplikan wajah hanya dengan persetujuan khusus. Kalau tidak ada persetujuan, cuplikan diburamkan atau tidak dipakai.

### 6.3 Retensi dan penghapusan

| Data | Disimpan sampai | Lalu |
|---|---|---|
| Video dan audio mentah pilot | evaluasi set uji selesai dan hasil diverifikasi, paling lama **12 bulan** sejak perekaman (usulan; disesuaikan dengan keputusan komite etik) | dihapus permanen, dengan berita acara penghapusan |
| Label (tanpa gambar) dan keluaran sistem | selama diperlukan untuk publikasi dan replikasi | disimpan dengan kode samaran |
| Daftar kode ke nama | sama dengan video mentah | dihapus bersamaan |
| Data relawan yang mundur | — | dihapus dalam 14 hari setelah permintaan, termasuk dari label bila memungkinkan |

### 6.4 Akses

- **Hanya tim penelitian yang disebut namanya** dalam protokol yang disetujui komite etik: pelabel, adjudikator, dan penanggung jawab.
- **Tidak termasuk** guru atau staf sekolah yang mengenal relawan, kecuali sebagai pelabel yang sudah menandatangani perjanjian kerahasiaan.
- Penyimpanan terenkripsi, tanpa layanan awan publik kecuali disetujui komite etik. Akses dicatat.
- Rekaman pilot **tidak boleh di-commit ke repositori**. `.gitignore` sudah mengecualikan `ai/eduai-ai/dataset_raw/`, `pilot/`, `preds/`, dan `evidence/`.

### 6.5 Data yang sudah ada

Repositori lokal sudah berisi dua kumpulan data yang asal persetujuannya **tidak tercatat**:
- `ai/eduai-ai/dataset_raw/`: 401 foto.
- `ai/eduai-ai/pilot/p01.mp4`: video pilot sekitar 3 menit.

Sebelum dipakai dalam evaluasi atau publikasi, perlu dipastikan siapa yang ada di dalamnya dan apakah persetujuannya sesuai bagian 6.1. Bila tidak dapat dipastikan, data itu sebaiknya tidak dipakai, lalu dihapus.

---

## 7. Celah antara protokol ini dan alat yang ada

`scripts/evaluate.py` dan `eval_behaviour.csv` **tidak diubah** dalam rangka dokumen ini. Yang sudah dan belum didukung:

| Kebutuhan protokol | `evaluate.py` sekarang |
|---|---|
| Precision, recall, F1, FP/jam per indikasi | **Ada**, tanpa interval kepercayaan |
| Pencocokan kejadian berbasis irisan waktu | **Ada** (`--min-overlap`). Pencocokannya rakus (*greedy*): tanda pertama yang cocok yang dipakai, bukan pencocokan optimal. Tidak ada toleransi awal ±2 detik. |
| `CANNOT_ANALYZE` | **Tidak dinilai.** Skrip hanya membaca kejadian berkategori `indication`. |
| Interval kepercayaan Wilson dan Poisson | Belum ada |
| Jam paparan per indikasi | Belum ada. FP/jam dibagi **total** jam semua video, termasuk masa pembentukan posisi normal dan periode tanpa audio. |
| Dua pelabel, Cohen's kappa, adjudikasi | Belum ada. `labels.csv` dibaca sebagai satu set label. |
| Analisis per kondisi | Belum ada. Kolom `intent`, `visibility`, `annotator`, dan `notes` di `labels.csv` ada tetapi tidak dibaca. |
| Pemisahan kalibrasi dan uji, pencatatan versi atau hash konfigurasi | Belum ada |
| Waktu sampai tanda | Belum ada |
| Tanda ganda dilaporkan terpisah | Belum ada; dihitung sebagai FP biasa |
| Kasus tanpa label dan tanpa prediksi | Skrip berhenti dengan error, karena memakai `rows[0]` pada daftar kosong. |

**Tentang `eval_behaviour.csv` saat ini.** Berkas ini berisi presisi dan recall 1,0 dengan FP/jam 0 untuk `FACE_ABSENT` dan `PHONE_VISIBLE`. Angka itu berasal dari **1 video sekitar 3 menit (0,05 jam) dengan 2 kejadian berlabel**, dilabeli satu orang. Dengan n=1 per indikasi, interval Wilson untuk recall kira-kira 0,21–1,00. Karena itu, angka ini **tidak boleh dikutip sebagai hasil akurasi**. Fungsinya hanya membuktikan bahwa skripnya berjalan.

Perluasan `evaluate.py` sesuai tabel di atas sebaiknya dikerjakan **sebelum** set uji dibuka, dan diuji dengan data buatan yang jawabannya sudah diketahui.

---

## 8. Keterbatasan yang wajib diungkap di publikasi

1. **Indikasi adalah aturan buatan tangan**, bukan model yang belajar dari perilaku ujian. Contohnya: "tidak ada wajah 5 detik", "menoleh 30° selama 3 detik".
2. **Model yang dipakai adalah model umum tanpa pelatihan ulang:** BlazeFace, Face Landmarker, EfficientDet-Lite0 yang dilatih pada COCO, dan YAMNet. Tidak ada yang dilatih atau disetel dengan data ujian. EduAI tidak memiliki fungsi pelatihan.
3. **Ambang bersifat sementara.** Versi `0.2-provisional` dipilih sebagai titik awal rekayasa, bukan dari literatur, dan belum dikalibrasi. Publikasi harus menyebut versi `config.yaml` yang diuji.
4. **Frame berasal dari perangkat siswa.** Pada mode browser dan mode Jitsi, browser siswa mengambil dan mengirim frame. Server hanya bisa memeriksa bahwa frame masih masuk. Server tidak bisa memastikan frame itu berasal dari kamera sungguhan, bukan rekaman atau kamera virtual.
5. **Belum pernah diuji dengan kamera fisik dan orang sungguhan.** Semua uji sejauh ini memakai kamera palsu Chrome atau berkas video. Itu mencakup uji dengan server Jitsi dan OpenVidu nyata.
6. **Perilaku yang tidak tercakup:** buku atau catatan tidak sah (belum ada detektor), layar atau perangkat kedua di luar bingkai, earphone, dan bantuan yang tidak tampak atau terdengar.
7. **Analisis bias berbasis sampel kecil** dan bersifat eksploratif (bagian 5.3).
8. **Indikasi bukan bukti pelanggaran.** Sistem dirancang sebagai alat bantu. Setiap indikasi harus ditinjau pengawas, dan hasil evaluasi tidak boleh dibaca sebagai kemampuan "mendeteksi kecurangan".
