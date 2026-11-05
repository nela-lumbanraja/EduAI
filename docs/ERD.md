# Diagram relasional database EduAI

Sumber: skema SQLite di `backend/app/db.py` (19 tabel, termasuk kolom tambahan dari migrasi). Gambar: [ERD.png](ERD.png).

- **Garis tegas**: relasi yang dideklarasikan sebagai `REFERENCES` (foreign key) di skema.
- **Garis putus-putus**: relasi logis. Kolomnya merujuk tabel lain, tetapi tanpa constraint foreign key. Tabel per siswa per ujian memakai pasangan `(exam_id, student_id)` yang sama dengan `exam_students`.

```mermaid
erDiagram
    users {
        int id PK
        text email UK
        text name
        text role "siswa | pengawas | penyelenggara | admin | sekolah"
        text password_hash
        text nis
        text class_name
        int active
        text created_at
    }
    exams {
        int id PK
        text name
        text description
        text subject
        text class_name
        text date
        text start_time
        int duration_min
        text status "Draft | Terjadwal | Sedang Berlangsung | Selesai"
        int supervisor_id FK "users.id"
        int monitoring_active
        text analysis_source
        text monitoring_started_at
        int created_by FK "users.id"
        text created_at
        text finished_at
    }
    exam_students {
        int exam_id PK, FK "exams.id, ON DELETE CASCADE"
        int student_id PK, FK "users.id"
    }
    consents {
        int exam_id PK
        int student_id PK
        text accepted_at
        text notice_version
        int audio_accepted
    }
    exam_seb {
        int exam_id PK, FK "exams.id, ON DELETE CASCADE"
        int required
        text config_keys
        text exam_keys
        text config_url
        int updated_by "users.id (logis)"
        text updated_at
    }
    seb_challenges {
        text nonce PK
        int exam_id
        int student_id
        real expires_at
    }
    seb_status {
        int exam_id PK
        int student_id PK
        text state
        text method
        text version
        text checked_at
    }
    presence {
        int exam_id PK
        int student_id PK
        text joined_at
        text last_seen
        text left_at
        int camera_on
        int mic_on
        text connection
        real rtt_ms
        text jitsi_state
    }
    ai_status {
        int exam_id PK
        int student_id PK
        text state
        text frame_status
        text reason
        int face_count
        real latency_ms
        text source
        text updated_at
    }
    events {
        text event_id PK
        int exam_id
        int student_id
        text indicator
        text category "indication | cannot_analyze | info"
        text status "open | closed"
        text start_ts
        text end_ts
        real score
        text reason
        text label
        text evidence_id "evidence.evidence_id (logis)"
        text model_version
        text config_version
        text schema_version
        text source
        text review_status
        text created_at
        text updated_at
        text details "JSON"
        text evidence_deleted_at
    }
    reviews {
        int id PK
        text event_id FK "events.event_id"
        int reviewer_id FK "users.id"
        text decision "Valid | Tidak Valid | Perlu Tinjauan Lanjut"
        text note
        text created_at
    }
    evidence {
        text evidence_id PK
        text event_id "events.event_id (logis)"
        int exam_id
        int student_id
        int frame_count
        text created_at
        text expires_at
    }
    report_frames {
        text event_id PK "events.event_id (logis)"
        int exam_id
        text frame_id
        text created_at
        text expires_at
        text deleted_at
    }
    manual_notes {
        int id PK
        int exam_id
        int student_id
        int author_id "users.id (logis)"
        text time_text
        text kind
        text note
        text created_at
    }
    connection_log {
        int id PK
        int exam_id
        int student_id
        text ts
        text state "connected | disconnected"
    }
    report_finals {
        int exam_id PK, FK "exams.id"
        int finalized_by FK "users.id"
        text finalized_by_name
        text finalized_at
    }
    exam_summaries {
        int exam_id PK, FK "exams.id"
        text kind "pre_end | final"
        text scheduled_end
        text created_at
        text payload "JSON"
    }
    workers {
        int exam_id PK
        int pid
        text started_at
        text last_heartbeat
        text models_json
        int students
    }
    audit {
        int id PK
        text ts
        int user_id "users.id (logis)"
        text user_name
        text role
        text action
        text target
        text status
    }

    %% Foreign key yang dideklarasikan
    users ||--o{ exams : "mengawasi (supervisor_id)"
    users ||--o{ exams : "membuat (created_by)"
    exams ||--o{ exam_students : "peserta"
    users ||--o{ exam_students : "siswa"
    exams ||--o| exam_seb : "pengaturan SEB"
    exams ||--o| report_finals : "laporan final"
    users ||--o{ report_finals : "memfinalkan"
    exams ||--o| exam_summaries : "ringkasan"
    events ||--o{ reviews : "ditinjau"
    users ||--o{ reviews : "peninjau"

    %% Relasi logis (tanpa constraint foreign key)
    exam_students ||..o| consents : "persetujuan"
    exam_students ||..o| presence : "kehadiran"
    exam_students ||..o| ai_status : "status AI"
    exam_students ||..o| seb_status : "status SEB"
    exam_students ||..o{ seb_challenges : "tantangan SEB"
    exam_students ||..o{ connection_log : "log koneksi"
    exam_students ||..o{ events : "kejadian"
    events ||..o| evidence : "bukti gambar"
    events ||..o| report_frames : "frame laporan"
    exams ||..o{ manual_notes : "catatan"
    users ||..o{ manual_notes : "penulis"
    exams ||..o| workers : "worker AI"
    users ||..o{ audit : "aktivitas"
```

Catatan:
- `presence`, `ai_status`, `seb_status`, dan `consents` menyimpan paling banyak satu baris per siswa per ujian (kunci primer `(exam_id, student_id)`).
- Kejadian berkategori `info` (label suara) disimpan di `events` dengan detail di kolom `details`. Kejadian ini tidak dihitung sebagai indikasi.
- `sqlite_sequence` adalah tabel internal SQLite untuk `AUTOINCREMENT` dan tidak digambar.
