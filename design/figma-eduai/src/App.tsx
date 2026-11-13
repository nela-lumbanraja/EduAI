import { useEffect, useState, type ReactNode } from "react"

type Page = "beranda" | "loading" | "masuk" | "siswa" | "pengawas" | "admin" | "sistem" | "my-exams" | "manage-exams" | "exam-monitoring" | "exam-sessions" | "live-monitoring" | "admin-dashboard"
type Role = "Siswa" | "Pengawas" | "Admin"
type LoginRole = "Student" | "Organizer" | "Proctor" | "Admin"

type IconName = "arrow" | "bell" | "book" | "calendar" | "camera" | "chart" | "check" | "chevron" | "clock" | "eye" | "file" | "head" | "home" | "lock" | "logout" | "menu" | "mic" | "monitor" | "phone" | "play" | "review" | "search" | "settings" | "shield" | "spark" | "users"

const iconPaths: Record<IconName, ReactNode> = {
  arrow: (
    <>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </>
  ),
  bell: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </>
  ),
  book: (
    <>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z" />
      <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M16 3v4M8 3v4M3 10h18" />
    </>
  ),
  camera: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="3" />
      <path d="m8 6 1.5-2h5L16 6" />
      <circle cx="12" cy="12.5" r="3" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  check: (
    <>
      <path d="m5 12 4 4L19 6" />
    </>
  ),
  chevron: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  file: (
    <>
      <path d="M6 2h8l4 4v16H6z" />
      <path d="M14 2v5h5M9 12h6M9 16h6" />
    </>
  ),
  head: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M5 21v-2a7 7 0 0 1 14 0v2M7 8H3m14 0h4" />
    </>
  ),
  home: (
    <>
      <path d="m3 11 9-8 9 8" />
      <path d="M5 10v11h14V10M9 21v-7h6v7" />
    </>
  ),
  lock: (
    <>
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  logout: (
    <>
      <path d="M10 5H5v14h5M14 8l4 4-4 4M18 12H9" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  mic: (
    <>
      <rect x="9" y="3" width="6" height="12" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
    </>
  ),
  monitor: (
    <>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <path d="M10 5h4M11 18h2" />
    </>
  ),
  play: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m10 8 6 4-6 4z" />
    </>
  ),
  review: (
    <>
      <path d="M4 4h16v13H8l-4 4z" />
      <path d="M8 9h8M8 13h5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 8.96 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15 1.7 1.7 0 0 0 3 14H3v-4h.08A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V3h4v.08A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9 1.7 1.7 0 0 0 21 10v4a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2 20 5v6c0 5.2-3.3 8.6-8 11-4.7-2.4-8-5.8-8-11V5z" />
      <path d="m8 12 2.5 2.5L16 9" />
    </>
  ),
  spark: (
    <>
      <path d="m12 2 1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5zM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7z" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20v-2a6 6 0 0 1 12 0v2M16 4.5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1" />
    </>
  ),
}

function Icon({
  name,
  size = 20,
  stroke = 1.8,
}: {
  name: IconName
  size?: number
  stroke?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {iconPaths[name]}
    </svg>
  )
}

function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <button
      className={`brand ${inverse ? "brand-inverse" : ""}`}
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="EduAI"
    >
      <span className="brand-mark">
        <Icon name="shield" size={20} stroke={2.2} />
      </span>
      <span>
        Edu<span>AI</span>
      </span>
    </button>
  )
}

function Status({
  children,
  tone,
}: {
  children: ReactNode
  tone: "red" | "amber" | "green" | "gray" | "blue"
}) {
  return (
    <span className={`status status-${tone}`}>
      <i />
      {children}
    </span>
  )
}

function HeroArtwork() {
  return (
    <div className="hero-art" aria-label="Ilustrasi perangkat ujian aman">
      <div className="orb orb-one" />
      <div className="orb orb-two" />
      <div className="glass-panel">
        <div className="webcam">
          <div className="webcam-lens">
            <div />
          </div>
          <div className="webcam-dot" />
        </div>
        <div className="laptop">
          <div className="laptop-screen">
            <div className="screen-top">
              <span />
              <span />
            </div>
            <div className="screen-person">
              <div className="person-head" />
              <div className="person-body" />
            </div>
            <div className="scan-corners">
              <i />
              <i />
              <i />
              <i />
            </div>
          </div>
          <div className="laptop-base" />
        </div>
        <div className="paper">
          <div className="paper-fold" />
          <i />
          <i />
          <i />
          <b>A</b>
          <b>B</b>
        </div>
        <div className="shield-3d">
          <svg viewBox="0 0 120 138" aria-hidden="true">
            <defs>
              <linearGradient
                id="shieldGradient"
                x1="15"
                y1="10"
                x2="100"
                y2="130"
                gradientUnits="userSpaceOnUse"
              >
                <stop stopColor="#f4d35e" />
                <stop offset="1" stopColor="#b68b16" />
              </linearGradient>
            </defs>
            <path
              d="M60 4 109 22v38c0 33-20 57-49 73C31 117 11 93 11 60V22Z"
              fill="#8a6810"
              opacity=".35"
              transform="translate(3 4)"
            />
            <path
              d="M60 4 109 22v38c0 33-20 57-49 73C31 117 11 93 11 60V22Z"
              fill="url(#shieldGradient)"
            />
            <path
              d="m36 66 15 15 34-38"
              fill="none"
              stroke="#14213D"
              strokeWidth="12"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M24 27 60 14"
              stroke="#fff"
              strokeOpacity=".38"
              strokeWidth="5"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <div className="secure-pill">
          <Icon name="lock" size={15} /> Sesi terenkripsi
        </div>
      </div>
    </div>
  )
}

function LegacyLanding({ go }: { go: (page: Page) => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const steps = [
    [
      "01",
      "Cek perangkat",
      "Kamera, mikrofon, dan koneksi diperiksa sebelum ujian dimulai.",
    ],
    [
      "02",
      "Persetujuan",
      "Siswa membaca penjelasan dan memberi persetujuan secara sadar.",
    ],
    [
      "03",
      "Ujian dipantau",
      "Sistem mencatat indikasi yang memerlukan perhatian pengawas.",
    ],
    [
      "04",
      "Pengawas meninjau",
      "Pengawas melihat konteks sebelum menentukan tindak lanjut.",
    ],
  ]
  const indicators = [
    [
      "Kehadiran wajah",
      "Mencatat saat wajah peserta tidak terlihat atau terdapat lebih dari satu wajah.",
    ],
    [
      "Arah kepala",
      "Menandai perubahan arah kepala yang terjadi berulang dalam periode tertentu.",
    ],
    [
      "Ponsel atau buku",
      "Mengenali objek yang tidak diperbolehkan di sekitar area ujian.",
    ],
    [
      "Suara di ruangan",
      "Mencatat adanya percakapan atau suara lain yang memerlukan pemeriksaan.",
    ],
    [
      "Aktivitas peramban",
      "Menandai perpindahan dari halaman ujian saat mode aman digunakan.",
    ],
  ]

  return (
    <div className="landing editorial-landing">
      <div className="institution-bar">
        <div>
          <span>EduAI untuk Sekolah Indonesia</span>
          <span>Pusat bantuan</span>
        </div>
      </div>
      <header className="topbar editorial-topbar">
        <div className="nav-wrap editorial-nav">
          <button
            className="editorial-logo"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          >
            Edu<span>AI</span>
          </button>
          <nav className={menuOpen ? "nav-open" : ""}>
            <a href="#beranda" onClick={() => setMenuOpen(false)}>
              Beranda
            </a>
            <a href="#cara-kerja" onClick={() => setMenuOpen(false)}>
              Cara Kerja
            </a>
            <a href="#privasi" onClick={() => setMenuOpen(false)}>
              Privasi
            </a>
            <button className="editorial-login" onClick={() => go("masuk")}>
              Masuk
            </button>
          </nav>
          <button
            className="menu-button"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Buka menu"
          >
            <Icon name="menu" />
          </button>
        </div>
      </header>

      <main>
        <section className="editorial-hero" id="beranda">
          <div className="editorial-hero-copy">
            <span className="section-label">
              Pengawasan ujian yang bertanggung jawab
            </span>
            <h1>Ujian online yang jujur, tanpa menuduh</h1>
            <p>
              EduAI membantu sekolah menjaga integritas ujian dengan memberi
              informasi yang jelas kepada pengawas—bukan membuat keputusan untuk
              mereka.
            </p>
            <button className="editorial-primary" onClick={() => go("masuk")}>
              Masuk <Icon name="arrow" size={18} />
            </button>
          </div>
          <figure className="hero-photo">
            <img
              src="https://images.unsplash.com/photo-1758612898304-1a6bb546ac44?auto=format&fit=crop&w=1400&q=85"
              alt="Siswa sedang mengerjakan tugas menggunakan laptop di meja belajar"
            />
            <figcaption>
              Pengawasan yang transparan membantu siswa tetap fokus dan merasa
              diperlakukan dengan adil.
            </figcaption>
          </figure>
        </section>

        <section className="editorial-process" id="cara-kerja">
          <div className="editorial-section-intro">
            <span className="section-label">Cara kerja</span>
            <h2>Proses yang jelas bagi siswa dan pengawas</h2>
            <p>
              Setiap tahap dijelaskan sebelum ujian dimulai. Tidak ada
              pemantauan tersembunyi.
            </p>
          </div>
          <div className="editorial-steps">
            {steps.map(([number, title, description]) => (
              <article key={title}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="editorial-statement">
          <div>
            <span className="statement-rule" />
            <blockquote>
              AI hanya menandai indikasi. Keputusan selalu di tangan pengawas.
            </blockquote>
            <p>Prinsip utama EduAI</p>
          </div>
        </section>

        <section className="monitoring-section" id="yang-dipantau">
          <div className="monitoring-heading">
            <span className="section-label">Yang dipantau</span>
            <h2>Informasi untuk membantu proses peninjauan</h2>
          </div>
          <div
            className="indicator-table"
            role="table"
            aria-label="Daftar indikasi yang dipantau"
          >
            <div className="indicator-row indicator-head" role="row">
              <span role="columnheader">Indikasi</span>
              <span role="columnheader">Keterangan</span>
            </div>
            {indicators.map(([name, description]) => (
              <div className="indicator-row" role="row" key={name}>
                <strong role="cell">{name}</strong>
                <p role="cell">{description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="editorial-privacy" id="privasi">
          <figure>
            <img
              src="https://images.unsplash.com/photo-1758685848208-e108b6af94cc?auto=format&fit=crop&w=1200&q=85"
              alt="Pengajar meninjau informasi pada layar laptop"
            />
            <figcaption>
              Data tinjauan hanya dapat diakses oleh pihak sekolah yang
              berwenang.
            </figcaption>
          </figure>
          <div>
            <span className="section-label">Privasi dan perlindungan data</span>
            <h2>Data hanya digunakan untuk keperluan pengawasan ujian</h2>
            <p>
              EduAI menerapkan prinsip minimisasi data. Sekolah menentukan siapa
              yang dapat mengakses data dan berapa lama data disimpan sesuai
              kebutuhan serta kebijakan yang berlaku.
            </p>
            <p>
              Siswa menerima penjelasan mengenai proses pengawasan sebelum
              memberi persetujuan. Rekaman tidak digunakan untuk tujuan lain.
            </p>
            <a href="#kebijakan" onClick={(event) => event.preventDefault()}>
              Kebijakan privasi <Icon name="arrow" size={17} />
            </a>
          </div>
        </section>

        <section className="editorial-contact">
          <div>
            <span className="section-label">Untuk sekolah</span>
            <h2>Bangun proses ujian yang dapat dipercaya bersama EduAI.</h2>
          </div>
          <button onClick={() => go("masuk")}>
            Masuk ke EduAI <Icon name="arrow" size={18} />
          </button>
        </section>
      </main>

      <footer className="editorial-footer">
        <div className="editorial-footer-grid">
          <div>
            <strong className="footer-logo">
              Edu<span>AI</span>
            </strong>
            <p>
              Sistem pengawasan ujian untuk sekolah Indonesia yang mengutamakan
              keadilan dan tanggung jawab manusia.
            </p>
          </div>
          <div>
            <h4>Informasi</h4>
            <a href="#cara-kerja">Cara kerja</a>
            <a href="#yang-dipantau">Yang dipantau</a>
            <a href="#privasi">Privasi</a>
          </div>
          <div>
            <h4>Dukungan</h4>
            <a href="mailto:bantuan@eduai.id">Pusat bantuan</a>
            <a href="mailto:bantuan@eduai.id">Hubungi kami</a>
            <button onClick={() => go("sistem")}>Sistem desain</button>
          </div>
        </div>
        <div className="editorial-footer-bottom">
          <span>© 2025 EduAI. Hak cipta dilindungi.</span>
          <span>Pendidikan yang jujur dimulai dari proses yang adil.</span>
        </div>
      </footer>
    </div>
  )
}

function PreviousHome({ go }: { go: (page: Page) => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<string | null>(null)
  const menuItems = [
    { label: "Home" },
    { label: "News", children: ["Latest news", "Product updates"] },
    { label: "How It Works", children: ["Exam process", "AI indications"] },
    {
      label: "Student Guide",
      children: ["Before the exam", "During the exam"],
    },
    {
      label: "Proctor Guide",
      children: ["Live sessions", "Reviewing reports"],
    },
    { label: "Privacy & Ethics", children: ["Consent", "Data protection"] },
    { label: "For Schools", children: ["School setup", "Request information"] },
    { label: "Contact" },
  ]
  const imageCards = [
    {
      title: "Device Check Before the Exam",
      description:
        "A quick check for cameras, microphones, browsers, and internet connections.",
      image:
        "https://images.unsplash.com/photo-1758612898304-1a6bb546ac44?auto=format&fit=crop&w=900&q=85",
      alt: "Student using a laptop at a desk",
    },
    {
      title: "Guide for Students",
      description: "What students need to know before joining an EduAI exam.",
      image:
        "https://images.unsplash.com/photo-1758270705172-07b53627dfcb?auto=format&fit=crop&w=900&q=85",
      alt: "Students gathered around a laptop",
    },
    {
      title: "Proctoring Reports",
      description:
        "Review indications with timestamps, context, and a clear decision record.",
      image:
        "https://images.unsplash.com/photo-1604525241109-c3b7eecf4add?auto=format&fit=crop&w=900&q=85",
      alt: "Teacher reviewing information on a laptop",
    },
    {
      title: "How EduAI's AI Works",
      description:
        "Understand what the system can flag—and what it never decides.",
      image:
        "https://images.unsplash.com/photo-1555436169-20e93ea9a7ff?auto=format&fit=crop&w=900&q=85",
      alt: "Two educators reviewing a laptop screen",
    },
    {
      title: "Privacy and Consent",
      description:
        "Plain-language information about consent, access, and data retention.",
      image:
        "https://images.unsplash.com/photo-1758685848208-e108b6af94cc?auto=format&fit=crop&w=900&q=85",
      alt: "Educator working at a laptop in a classroom",
    },
  ]

  return (
    <div className="local-home">
      <header>
        <div className="local-utility">
          <div className="local-width">
            <button
              className="local-logo"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              Edu<span>AI</span>
            </button>
            <div className="utility-links">
              <a href="#schools">Schools &amp; Classes</a>
              <button onClick={() => go("siswa")}>Student Portal</button>
              <button className="search-button" aria-label="Search">
                <Icon name="search" size={21} />
              </button>
            </div>
          </div>
        </div>

        <div className="local-title-row">
          <div className="local-width">
            <a href="#home">EduAI – Fair Online Exams</a>
            <button
              className="local-menu-button"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-expanded={menuOpen}
            >
              <Icon name="menu" size={22} />
              <span>Menu</span>
            </button>
          </div>
        </div>

        <nav
          className={
            menuOpen ? "local-main-nav menu-is-open" : "local-main-nav"
          }
          aria-label="Main navigation"
        >
          <div className="local-width">
            {menuItems.map((item, index) => (
              <div
                className={`local-nav-item ${index === 0 ? "active" : ""}`}
                key={item.label}
              >
                {item.children ? (
                  <>
                    <button
                      onClick={() =>
                        setOpenDropdown(
                          openDropdown === item.label ? null : item.label,
                        )
                      }
                      aria-expanded={openDropdown === item.label}
                    >
                      {item.label}
                      <Icon name="chevron" size={14} />
                    </button>
                    <div
                      className={
                        openDropdown === item.label
                          ? "local-submenu submenu-open"
                          : "local-submenu"
                      }
                    >
                      {item.children.map((child) => (
                        <a
                          href="#content"
                          key={child}
                          onClick={() => setMenuOpen(false)}
                        >
                          {child}
                        </a>
                      ))}
                    </div>
                  </>
                ) : (
                  <a
                    href={index === 0 ? "#home" : "#contact"}
                    onClick={() => setMenuOpen(false)}
                  >
                    {item.label}
                  </a>
                )}
              </div>
            ))}
          </div>
        </nav>
      </header>

      <main id="home">
        <section className="vision-section local-width">
          <h1>Our vision</h1>
          <p>
            Helping schools keep online exams honest without accusing students.
            AI only flags indications; proctors always make the decision.
          </p>
        </section>

        <section className="featured-section local-width">
          <div className="featured-copy">
            <span className="content-label">Featured</span>
            <h2>EduAI Sprint 3 launch</h2>
            <p>
              See the newest improvements to exam setup, safer browser controls,
              and clearer evidence review for school proctors.
            </p>
            <a href="#content">
              Read more <Icon name="arrow" size={17} />
            </a>
          </div>
          <figure className="video-feature">
            <div className="video-frame">
              <img
                src="https://images.unsplash.com/photo-1758270705172-07b53627dfcb?auto=format&fit=crop&w=1400&q=85"
                alt="Students discussing work around a laptop in a classroom"
              />
              <button aria-label="Play EduAI Sprint 3 launch video">
                <Icon name="play" size={44} stroke={1.3} />
              </button>
              <span>03:18</span>
            </div>
            <figcaption>
              EduAI Sprint 3: a short overview for students, proctors, and
              school leaders.
            </figcaption>
          </figure>
        </section>

        <section className="home-grid-section local-width" id="content">
          <h2>Explore EduAI</h2>
          <div className="local-card-grid">
            {imageCards.map((card, index) => (
              <article
                className={`local-image-card card-${index + 1}`}
                key={card.title}
              >
                <img src={card.image} alt={card.alt} />
                <div>
                  <h3>
                    <a href="#content">{card.title}</a>
                  </h3>
                  <p>{card.description}</p>
                </div>
              </article>
            ))}
            <article className="local-text-card news-card">
              <h3>Latest News</h3>
              <ul>
                <li>
                  <a href="#content">Jitsi exam mode now available</a>
                </li>
                <li>
                  <a href="#content">Safe Exam Browser per exam</a>
                </li>
                <li>
                  <a href="#content">Book and phone detection test results</a>
                </li>
              </ul>
            </article>
            <article className="local-text-card proctor-card">
              <h3>For Proctors and Admins</h3>
              <p>
                Manage live exams, review indications, and keep a clear decision
                record.
              </p>
              <button onClick={() => go("pengawas")}>
                Go to dashboard <Icon name="arrow" size={16} />
              </button>
            </article>
            <article className="local-text-card updates-card">
              <h3>Updates</h3>
              <p>
                Get occasional notes about EduAI releases, guidance, and school
                pilots.
              </p>
              <a href="mailto:updates@eduai.id">
                Sign up for email updates <Icon name="arrow" size={16} />
              </a>
            </article>
          </div>
        </section>

        <section className="connected-section local-width">
          <p className="last-updated">Last updated: 5 November 2026</p>
          <div className="connected-row">
            <h2>Stay connected</h2>
            <div className="social-links">
              <a href="#contact">Instagram</a>
              <a href="#contact">YouTube</a>
              <a href="#contact">GitHub</a>
              <a href="#contact">Blog</a>
            </div>
            <div className="secondary-links">
              <a href="#content">Updates</a>
              <a href="#content">How we use data</a>
            </div>
          </div>
        </section>
      </main>

      <footer className="local-footer" id="contact">
        <div className="local-width">
          <h2>EduAI – Smart Exam Integrity</h2>
          <div className="footer-policy-grid">
            <nav aria-label="Policy links">
              <a href="#contact">Terms of use</a>
              <a href="#contact">Privacy &amp; cookies</a>
              <a href="#contact">Complaints</a>
              <a href="#contact">Accessibility</a>
              <a href="#contact">Data protection</a>
              <a href="#contact">AI policy</a>
            </nav>
            <div className="partner-area">
              <span>School technology partners</span>
              <div
                className="partner-marks"
                aria-label="Partner logo placeholders"
              >
                <i>SEB</i>
                <i>JITSI</i>
                <i>EDU</i>
              </div>
            </div>
          </div>
          <div className="local-footer-bottom">
            <button onClick={() => go("masuk")}>Log in</button>
            <span>© 2026 EduAI</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

function Landing({
  go,
  startLoginLoading,
}: {
  go: (page: Page, loginRole?: LoginRole) => void
  startLoginLoading: (role: LoginRole) => void
}) {
  const [activeSignal, setActiveSignal] = useState<string | null>(null)
  const cards = [
    {
      title: "Device check",
      text: "Check your camera, microphone, browser, and connection before the exam.",
      image:
        "https://images.unsplash.com/photo-1758612898304-1a6bb546ac44?auto=format&fit=crop&w=900&q=85",
      alt: "Student completing school work on a laptop",
    },
    {
      title: "Student guide",
      text: "A clear guide to preparing for and completing an EduAI exam.",
      image:
        "https://images.unsplash.com/photo-1758270705172-07b53627dfcb?auto=format&fit=crop&w=900&q=85",
      alt: "Students studying together around a laptop",
    },
    {
      title: "Proctor reports",
      text: "Review possible issues with timestamps, context, and decision notes.",
      image:
        "https://images.unsplash.com/photo-1604525241109-c3b7eecf4add?auto=format&fit=crop&w=900&q=85",
      alt: "Teacher reviewing a report on a laptop",
    },
    {
      title: "How the AI works",
      text: "Learn what EduAI can flag and why it never makes the final decision.",
      image:
        "https://images.unsplash.com/photo-1555436169-20e93ea9a7ff?auto=format&fit=crop&w=900&q=85",
      alt: "Educators reviewing information on a laptop",
    },
    {
      title: "Privacy and consent",
      text: "Understand how exam data is collected, protected, and deleted.",
      image:
        "https://images.unsplash.com/photo-1758685848208-e108b6af94cc?auto=format&fit=crop&w=900&q=85",
      alt: "Teacher using a laptop in a classroom",
    },
  ]

  return (
    <div className="simple-home">
      <div className="simple-topbar">
        <div className="simple-width">
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          >
            EduAI
          </button>
          <nav aria-label="Utility navigation">
            <button onClick={() => startLoginLoading("Organizer")}>
              Schools
            </button>
            <button onClick={() => startLoginLoading("Student")}>
              Student Portal
            </button>
            <button aria-label="Search">
              <Icon name="search" size={18} />
            </button>
          </nav>
        </div>
      </div>

      <header className="simple-header">
        <div className="simple-width">
          <a className="simple-title" href="#home">
            EduAI Exams
          </a>
          <nav aria-label="Main navigation">
            <a className="active" href="#home">
              Home
            </a>
            <a href="#news">News</a>
            <a href="#approach">How It Works</a>
            <a href="#students">Students</a>
            <a href="#proctors">Proctors</a>
            <a href="#privacy">Privacy</a>
            <a href="#footer">Contact</a>
          </nav>
        </div>
      </header>

      <main id="home">
        <section className="simple-intro simple-width">
          <div className="simple-intro-copy">
            <h1>Our vision</h1>
            <p>
              We help schools run fair online exams.
              <br />
              AI only flags possible issues.
              <br />
              Teachers make the final decision.
            </p>
            <a href="#approach">
              Read our approach <span>→</span>
            </a>
          </div>
          <figure className="simple-video">
            <div>
              <img
                src="https://images.unsplash.com/photo-1678680239675-9b457919b7a8?auto=format&fit=crop&w=1000&q=85"
                alt="Students working at a table with laptops"
              />
              <button aria-label="Play overview video">
                <Icon name="play" size={39} stroke={1.4} />
              </button>
            </div>
            <figcaption>
              How EduAI supports fair decisions in online exams.
            </figcaption>
          </figure>
        </section>

        <section className="simple-grid simple-width" id="approach">
          {cards.map((card, index) => (
            <article
              id={
                index === 1
                  ? "students"
                  : index === 2
                    ? "proctors"
                    : index === 4
                      ? "privacy"
                      : undefined
              }
              key={card.title}
            >
              <img src={card.image} alt={card.alt} />
              <h2>
                <a href="#approach">{card.title}</a>
              </h2>
              <p>{card.text}</p>
            </article>
          ))}
          <article className="simple-news-card" id="news">
            <h2>Latest news</h2>
            <ul>
              <li>
                <a href="#news">Jitsi exam mode now available</a>
              </li>
              <li>
                <a href="#news">Safe Exam Browser per exam</a>
              </li>
              <li>
                <a href="#news">Book and phone detection test results</a>
              </li>
            </ul>
          </article>
        </section>

        <section className="ai-signals-section">
          <div className="simple-width">
            <div className="ai-signals-heading">
              <h2>What the AI looks for</h2>
              <p>
                These are signs, not proof. A teacher always checks them first.
              </p>
            </div>
            <div className="ai-mosaic">
              {[
                [
                  [
                    "Phone in view",
                    "Using or holding a phone during the exam.",
                    "/images/ai-signals/1_phone_in_view.png",
                  ],
                  [
                    "Book or notes in view",
                    "Books, notes, or papers in front of the camera.",
                    "/images/ai-signals/2_book_in_view.png",
                  ],
                ],
                [
                  [
                    "Another person in view",
                    "A second face appears on camera.",
                    "/images/ai-signals/3_another_person.png",
                  ],
                  [
                    "Looking away often",
                    "Turning away from the screen many times.",
                    "/images/ai-signals/4_looking_away.png",
                  ],
                ],
                [
                  [
                    "Face not visible",
                    "Leaving the camera or covering it.",
                    "/images/ai-signals/5_face_not_visible.png",
                  ],
                  [
                    "Other voice heard",
                    "Talking or another voice during the exam.",
                    "/images/ai-signals/6_other_voice.png",
                  ],
                ],
              ].map((column, columnIndex) => (
                <div
                  className={`ai-mosaic-column column-${columnIndex + 1}`}
                  key={columnIndex}
                >
                  {column.map(([title, description, image]) => (
                    <article
                      className={`${activeSignal === title ? "active" : ""} ${
                        title === "Other voice heard" ? "no-gold" : ""
                      }`}
                      key={title}
                      role="button"
                      tabIndex={0}
                      aria-pressed={activeSignal === title}
                      aria-disabled={title === "Other voice heard"}
                      onClick={() => {
                        if (title !== "Other voice heard") {
                          setActiveSignal(title)
                        }
                      }}
                      onKeyDown={(event) => {
                        if (
                          title !== "Other voice heard" &&
                          (event.key === "Enter" || event.key === " ")
                        ) {
                          event.preventDefault()
                          setActiveSignal(title)
                        }
                      }}
                    >
                      <img
                        className={`ai-mosaic-photo ${
                          title === "Phone in view" ||
                          title === "Book or notes in view"
                            ? "photo-low"
                            : ""
                        }`}
                        src={image}
                        alt={title}
                      />
                      <div className="ai-mosaic-overlay" />
                      <div className="ai-mosaic-copy">
                        <h3>{title}</h3>
                        <p>{description}</p>
                      </div>
                    </article>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <div className="simple-width">
            <p className="cannot-analyse-note">
              If the camera is too dark or blurry, it is marked &apos;Cannot
              analyse&apos;, not as cheating.
            </p>
          </div>
        </section>

        <section className="simple-connect">
          <div>
            <h2>Stay connected</h2>
            <p>
              Receive occasional news about EduAI releases, guidance, and school
              pilots.
            </p>
            <a href="mailto:updates@eduai.id">Get updates</a>
          </div>
        </section>
      </main>

      <footer className="simple-footer" id="footer">
        <div className="simple-width">
          <div>
            <h2>EduAI</h2>
            <p>
              A school exam proctoring project built around fairness, privacy,
              and human judgement.
            </p>
          </div>
          <nav aria-label="Policy links">
            <a href="#footer">Terms</a>
            <a href="#footer">Privacy</a>
            <a href="#footer">Accessibility</a>
            <a href="#footer">AI policy</a>
          </nav>
          <div className="simple-footer-meta">
            <button onClick={() => go("masuk", "Student")}>Log in</button>
            <span>© 2026 EduAI</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

function LegacyLogin({ go }: { go: (page: Page) => void }) {
  const [role, setRole] = useState<Role>("Siswa")
  const [showPassword, setShowPassword] = useState(false)
  const roleInfo = {
    Siswa: ["book" as IconName, "Ikuti ujian dengan aman"],
    Pengawas: ["eye" as IconName, "Pantau dan tinjau ujian"],
    Admin: ["settings" as IconName, "Kelola sekolah dan pengguna"],
  }
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    go(role === "Siswa" ? "siswa" : role === "Pengawas" ? "pengawas" : "admin")
  }
  return (
    <div className="login-page">
      <button className="login-back" onClick={() => go("beranda")}>
        <Icon name="arrow" size={18} /> Kembali ke beranda
      </button>
      <div className="login-brand">
        <Brand />
      </div>
      <div className="login-shell">
        <section className="login-card">
          <span className="login-lock">
            <Icon name="lock" size={22} />
          </span>
          <h1>Selamat datang kembali</h1>
          <p>Pilih peran dan masuk ke akun EduAI Anda.</p>
          <div className="role-tabs">
            {(Object.keys(roleInfo) as Role[]).map((item) => (
              <button
                className={role === item ? "active" : ""}
                onClick={() => setRole(item)}
                key={item}
              >
                <Icon name={roleInfo[item][0] as IconName} size={19} />
                {item}
              </button>
            ))}
          </div>
          <div className="role-caption">
            <Icon name={roleInfo[role][0] as IconName} size={16} />{" "}
            {roleInfo[role][1]}
          </div>
          <form onSubmit={submit}>
            <label>
              Email atau NIS/NIP
              <input
                type="text"
                defaultValue={role === "Siswa" ? "alya.pratama" : ""}
                placeholder="Masukkan identitas Anda"
                required
              />
            </label>
            <label>
              Kata sandi
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  defaultValue="EduAI2025"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <Icon name="eye" size={19} />
                </button>
              </div>
            </label>
            <div className="form-options">
              <label>
                <input type="checkbox" /> Ingat saya
              </label>
              <button type="button">Lupa kata sandi?</button>
            </div>
            <button
              className="button button-primary login-submit"
              type="submit"
            >
              Masuk sebagai {role}
              <Icon name="arrow" size={18} />
            </button>
          </form>
          <div className="secure-note">
            <Icon name="shield" size={18} /> Koneksi Anda aman dan terenkripsi
          </div>
        </section>
        <aside className="login-aside">
          <div className="quote-mark">“</div>
          <blockquote>
            Teknologi seharusnya membantu kita melihat lebih jelas, bukan
            menggantikan penilaian manusia.
          </blockquote>
          <p>Prinsip pengawasan EduAI</p>
          <div className="mini-illustration">
            <div className="mini-shield">
              <Icon name="shield" size={58} stroke={1.5} />
            </div>
            <div className="mini-paper">
              <i />
              <i />
              <i />
            </div>
          </div>
        </aside>
      </div>
      <p className="login-help">
        Butuh bantuan?{" "}
        <a href="mailto:bantuan@eduai.id">Hubungi pusat dukungan</a>
      </p>
    </div>
  )
}

const navByRole: Record<Role, [IconName, string][]> = {
  Siswa: [
    ["home", "Ringkasan"],
    ["calendar", "Jadwal Ujian"],
    ["file", "Riwayat"],
    ["settings", "Pengaturan"],
  ],
  Pengawas: [
    ["home", "Ringkasan"],
    ["eye", "Ujian Aktif"],
    ["review", "Tinjauan"],
    ["file", "Laporan"],
  ],
  Admin: [
    ["home", "Ringkasan"],
    ["users", "Pengguna"],
    ["book", "Mata Pelajaran"],
    ["settings", "Pengaturan"],
  ],
}

function DashboardShell({
  role,
  go,
  children,
}: {
  role: Role
  go: (page: Page) => void
  children: ReactNode
}) {
  const [mobileNav, setMobileNav] = useState(false)
  return (
    <div className="dashboard">
      <aside className={mobileNav ? "sidebar sidebar-open" : "sidebar"}>
        <div className="sidebar-brand">
          <Brand inverse />
        </div>
        <nav>
          <span className="nav-label">MENU UTAMA</span>
          {navByRole[role].map(([icon, label], index) => (
            <button className={index === 0 ? "active" : ""} key={label}>
              <Icon name={icon} size={19} />
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="school-chip">
            <span>SN</span>
            <div>
              <strong>SMA Nusantara</strong>
              <small>Jakarta Selatan</small>
            </div>
          </div>
          <button onClick={() => go("beranda")}>
            <Icon name="logout" size={18} /> Keluar
          </button>
        </div>
      </aside>
      <div className="dash-main">
        <header className="dash-header">
          <button
            className="dash-menu"
            onClick={() => setMobileNav(!mobileNav)}
          >
            <Icon name="menu" />
          </button>
          <div className="dash-title-mobile">
            <Brand />
          </div>
          <div className="header-actions">
            <button className="help-button">Pusat Bantuan</button>
            <div className="avatar">AP</div>
            <div className="profile-name">
              <strong>
                {role === "Siswa"
                  ? "Alya Pratama"
                  : role === "Pengawas"
                    ? "Bapak Dimas"
                    : "Rina Wulandari"}
              </strong>
              <span>{role}</span>
            </div>
            <Icon name="chevron" size={16} />
          </div>
        </header>
        <main className="dash-content">{children}</main>
      </div>
    </div>
  )
}

function StudentDashboard({ go }: { go: (page: Page) => void }) {
  const [ready, setReady] = useState(false)
  return (
    <DashboardShell role="Siswa" go={go}>
      <div className="welcome-row">
        <div>
          <span className="dash-kicker">SELASA, 18 FEBRUARI 2025</span>
          <h1>Selamat pagi, Alya</h1>
          <p>Berikut kegiatan ujianmu hari ini.</p>
        </div>
        <div className="integrity-card">
          <Icon name="shield" size={28} />
          <div>
            <strong>Status perangkat</strong>
            <span>Semua sistem normal</span>
          </div>
          <Status tone="green">Siap</Status>
        </div>
      </div>
      <section className="next-exam">
        <div className="exam-date">
          <strong>18</strong>
          <span>FEB</span>
        </div>
        <div className="exam-info">
          <span className="dash-kicker">UJIAN BERIKUTNYA · 09.00 WIB</span>
          <h2>Matematika Wajib</h2>
          <p>Kelas XII IPA · 90 menit · 40 soal</p>
          <div className="exam-tags">
            <span>
              <Icon name="camera" size={15} /> Kamera
            </span>
            <span>
              <Icon name="mic" size={15} /> Mikrofon
            </span>
            <span>
              <Icon name="lock" size={15} /> Browser Aman
            </span>
          </div>
        </div>
        <button className="button button-gold" onClick={() => setReady(true)}>
          {ready ? "Perangkat siap" : "Cek perangkat"}
          <Icon name={ready ? "check" : "arrow"} size={18} />
        </button>
      </section>
      {ready && (
        <div className="success-banner">
          <Icon name="check" size={19} />
          <div>
            <strong>Pemeriksaan selesai</strong>
            <span>
              Kamera, mikrofon, dan koneksi internet berfungsi dengan baik.
            </span>
          </div>
        </div>
      )}
      <div className="content-grid">
        <section className="flat-card schedule-card">
          <div className="card-heading">
            <div>
              <h2>Jadwal mendatang</h2>
              <p>Tiga ujian dalam tujuh hari ke depan</p>
            </div>
            <button>
              Lihat semua <Icon name="arrow" size={16} />
            </button>
          </div>
          {[
            ["20", "FEB", "Bahasa Indonesia", "08.00 · 120 menit"],
            ["22", "FEB", "Fisika", "10.30 · 90 menit"],
            ["24", "FEB", "Bahasa Inggris", "08.00 · 90 menit"],
          ].map((item, i) => (
            <div className="schedule-item" key={item[2]}>
              <div className="date-mini">
                <b>{item[0]}</b>
                <span>{item[1]}</span>
              </div>
              <div>
                <strong>{item[2]}</strong>
                <span>{item[3]}</span>
              </div>
              <Status tone={i === 0 ? "blue" : "gray"}>
                {i === 0 ? "2 hari lagi" : "Terjadwal"}
              </Status>
              <Icon name="chevron" size={18} />
            </div>
          ))}
        </section>
        <section className="flat-card prep-card">
          <div className="card-heading">
            <div>
              <h2>Persiapan ujian</h2>
              <p>Selesaikan sebelum mulai</p>
            </div>
          </div>
          {[
            ["monitor" as IconName, "Perangkat kompatibel", true],
            ["camera" as IconName, "Kamera & mikrofon", ready],
            ["book" as IconName, "Baca tata tertib", false],
          ].map(([icon, label, done]) => (
            <div className="prep-item" key={label as string}>
              <span className={done ? "done prep-icon" : "prep-icon"}>
                <Icon name={icon as IconName} size={19} />
              </span>
              <strong>{label}</strong>
              {done ? (
                <Icon name="check" size={18} />
              ) : (
                <button onClick={() => setReady(true)}>Periksa</button>
              )}
            </div>
          ))}
          <div className="privacy-mini">
            <Icon name="lock" size={17} />
            <p>
              <strong>Privasi Anda terlindungi</strong>
              <br />
              Data digunakan hanya selama proses pengawasan ujian.
            </p>
          </div>
        </section>
      </div>
    </DashboardShell>
  )
}

function ProctorDashboard({ go }: { go: (page: Page) => void }) {
  const [reviewed, setReviewed] = useState(false)
  return (
    <DashboardShell role="Pengawas" go={go}>
      <div className="welcome-row">
        <div>
          <span className="dash-kicker">RUANG PENGAWAS</span>
          <h1>Ringkasan pengawasan</h1>
          <p>
            Pantau sesi aktif dan prioritaskan kejadian yang perlu ditinjau.
          </p>
        </div>
        <button className="button button-primary">
          <Icon name="eye" size={18} /> Buka ujian aktif
        </button>
      </div>
      <div className="stat-grid">
        <Stat
          icon="users"
          value="128"
          label="Siswa aktif"
          trend="+12 baru masuk"
        />
        <Stat
          icon="eye"
          value="4"
          label="Sesi berlangsung"
          trend="Semua terhubung"
        />
        <Stat
          icon="review"
          value={reviewed ? "6" : "7"}
          label="Perlu ditinjau"
          trend="Prioritas hari ini"
          alert
        />
        <Stat
          icon="check"
          value="93%"
          label="Sesi lancar"
          trend="+2,4% minggu ini"
        />
      </div>
      <section className="flat-card review-table-card">
        <div className="card-heading">
          <div>
            <h2>Antrean tinjauan</h2>
            <p>Indikasi diurutkan berdasarkan waktu dan tingkat prioritas</p>
          </div>
          <div className="table-actions">
            <button>
              <Icon name="search" size={17} /> Cari
            </button>
            <button>
              Filter <Icon name="chevron" size={15} />
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Siswa</th>
                <th>Ujian</th>
                <th>Indikasi</th>
                <th>Waktu</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {[
                [
                  "DN",
                  "Dito Nugraha",
                  "Matematika Wajib",
                  "Objek ponsel",
                  "09.34.12",
                  "Terindikasi",
                ],
                [
                  "SK",
                  "Siti Khadijah",
                  "Matematika Wajib",
                  "Arah kepala",
                  "09.28.40",
                  "Perlu Ditinjau",
                ],
                [
                  "RF",
                  "Rafi Firdaus",
                  "Fisika",
                  "Lebih dari satu wajah",
                  "08.52.03",
                  "Tidak Dapat Dianalisis",
                ],
              ].map((row, i) => (
                <tr key={row[1]}>
                  <td>
                    <div className="table-person">
                      <span>{row[0]}</span>
                      <strong>{row[1]}</strong>
                    </div>
                  </td>
                  <td>{row[2]}</td>
                  <td>
                    <b>{row[3]}</b>
                  </td>
                  <td>{row[4]}</td>
                  <td>
                    <Status tone={i === 0 ? "red" : i === 1 ? "amber" : "gray"}>
                      {reviewed && i === 0 ? "Valid" : row[5]}
                    </Status>
                  </td>
                  <td>
                    <button
                      className="review-btn"
                      onClick={() => i === 0 && setReviewed(true)}
                    >
                      {reviewed && i === 0 ? "Selesai" : "Tinjau"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardShell>
  )
}

function Stat({
  icon,
  value,
  label,
  trend,
  alert,
}: {
  icon: IconName
  value: string
  label: string
  trend: string
  alert?: boolean
}) {
  return (
    <article className="stat-card">
      <span className={alert ? "stat-icon alert" : "stat-icon"}>
        <Icon name={icon} size={22} />
      </span>
      <div>
        <strong>{value}</strong>
        <p>{label}</p>
        <small>{trend}</small>
      </div>
    </article>
  )
}

function AdminDashboard({ go }: { go: (page: Page) => void }) {
  return (
    <DashboardShell role="Admin" go={go}>
      <div className="welcome-row">
        <div>
          <span className="dash-kicker">ADMINISTRASI SEKOLAH</span>
          <h1>Dasbor sekolah</h1>
          <p>Kelola akses, ujian, dan kebijakan pengawasan dari satu tempat.</p>
        </div>
        <button className="button button-primary">
          <Icon name="users" size={18} /> Tambah pengguna
        </button>
      </div>
      <div className="stat-grid">
        <Stat
          icon="users"
          value="1.284"
          label="Total pengguna"
          trend="1.120 siswa · 164 staf"
        />
        <Stat
          icon="book"
          value="18"
          label="Ujian bulan ini"
          trend="6 sedang dipersiapkan"
        />
        <Stat
          icon="shield"
          value="98,2%"
          label="Kepatuhan perangkat"
          trend="+1,8% dari bulan lalu"
        />
        <Stat
          icon="chart"
          value="42"
          label="Laporan selesai"
          trend="Semua telah ditinjau"
        />
      </div>
      <div className="admin-grid">
        <section className="flat-card">
          <div className="card-heading">
            <div>
              <h2>Aktivitas ujian</h2>
              <p>Jumlah sesi dalam enam bulan terakhir</p>
            </div>
            <button>
              Tahun ajaran 2024/25 <Icon name="chevron" size={15} />
            </button>
          </div>
          <div className="bar-chart">
            {[42, 58, 47, 76, 62, 90].map((height, i) => (
              <div key={i}>
                <i style={{ height: `${height}%` }} />
                <span>{["Sep", "Okt", "Nov", "Des", "Jan", "Feb"][i]}</span>
              </div>
            ))}
          </div>
        </section>
        <section className="flat-card">
          <div className="card-heading">
            <div>
              <h2>Pengaturan cepat</h2>
              <p>Kebijakan yang sering digunakan</p>
            </div>
          </div>
          {[
            ["clock" as IconName, "Retensi data", "30 hari"],
            ["shield" as IconName, "Tingkat sensitivitas", "Seimbang"],
            ["review" as IconName, "Alur tinjauan", "Dua tahap"],
          ].map((item) => (
            <button className="setting-row" key={item[1]}>
              <span>
                <Icon name={item[0]} size={19} />
              </span>
              <div>
                <strong>{item[1]}</strong>
                <p>{item[2]}</p>
              </div>
              <Icon name="chevron" size={18} />
            </button>
          ))}
        </section>
      </div>
    </DashboardShell>
  )
}

function DesignSystem({ go }: { go: (page: Page) => void }) {
  return (
    <div className="system-page">
      <header>
        <Brand />
        <button
          className="button button-secondary"
          onClick={() => go("beranda")}
        >
          <Icon name="arrow" size={17} /> Kembali
        </button>
      </header>
      <main>
        <span className="kicker">Fondasi visual</span>
        <h1>Sistem Desain EduAI</h1>
        <p className="system-lead">
          Komponen yang konsisten, mudah dibaca, dan inklusif untuk seluruh
          pengalaman ujian.
        </p>
        <section>
          <h2>Warna</h2>
          <div className="swatches">
            {[
              ["Navy Utama", "#14213D"],
              ["Emas EduAI", "#C9A227"],
              ["Latar Hangat", "#F7F6F2"],
              ["Tinta", "#20293A"],
              ["Berhasil", "#23856D"],
            ].map((item) => (
              <div className="swatch" key={item[0]}>
                <i style={{ background: item[1] }} />
                <strong>{item[0]}</strong>
                <span>{item[1]}</span>
              </div>
            ))}
          </div>
        </section>
        <section>
          <h2>Tipografi</h2>
          <div className="type-sample">
            <div>
              <span>Judul utama · 56/60</span>
              <h3>Jelas, adil, dan tepercaya.</h3>
            </div>
            <div>
              <span>Teks isi · 16/26</span>
              <p>
                Bahasa yang sederhana membantu setiap pengguna memahami proses
                pengawasan ujian.
              </p>
            </div>
          </div>
        </section>
        <section>
          <h2>Tombol & status</h2>
          <div className="component-row">
            <button className="button button-primary">Tombol utama</button>
            <button className="button button-secondary">Tombol sekunder</button>
            <Status tone="red">Terindikasi</Status>
            <Status tone="amber">Perlu Ditinjau</Status>
            <Status tone="green">Valid</Status>
            <Status tone="gray">Tidak Valid</Status>
            <Status tone="blue">Tidak Dapat Dianalisis</Status>
          </div>
        </section>
        <section>
          <h2>Kartu & tabel</h2>
          <div className="system-card-demo">
            <div>
              <span className="stat-icon">
                <Icon name="shield" />
              </span>
              <strong>Integritas terjaga</strong>
              <p>Informasi penting disajikan dengan hierarki yang tenang.</p>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Peserta</th>
                  <th>Ujian</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Alya Pratama</td>
                  <td>Matematika</td>
                  <td>
                    <Status tone="green">Valid</Status>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

function LoginLoadingScreen({ onComplete }: { onComplete: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onComplete, 1500)
    return () => window.clearTimeout(timer)
  }, [onComplete])

  return (
    <main className="login-loading-screen" aria-live="polite">
      <div className="login-loading-content">
        <div className="login-loading-rocket-stage" aria-hidden="true">
          <div className="login-loading-rocket">
            <svg viewBox="0 0 84 130">
              <defs>
                <linearGradient
                  id="loadingRocketBody"
                  x1="17"
                  y1="8"
                  x2="67"
                  y2="104"
                >
                  <stop offset="0" stopColor="#FFFFFF" />
                  <stop offset=".6" stopColor="#F2F1EC" />
                  <stop offset="1" stopColor="#C9CED5" />
                </linearGradient>
                <linearGradient
                  id="loadingRocketGold"
                  x1="12"
                  y1="20"
                  x2="57"
                  y2="95"
                >
                  <stop offset="0" stopColor="#E6C95E" />
                  <stop offset="1" stopColor="#A77E10" />
                </linearGradient>
              </defs>
              <path
                d="M42 4C25 19 20 40 21 77l21 21 21-21C64 40 59 19 42 4Z"
                fill="url(#loadingRocketBody)"
              />
              <path d="M21 63 7 91l18-7Z" fill="url(#loadingRocketGold)" />
              <path d="m63 63 14 28-18-7Z" fill="url(#loadingRocketGold)" />
              <path d="m31 91 11 20 11-20Z" fill="#C9A227" />
              <circle cx="42" cy="44" r="11" fill="#14213D" />
              <circle cx="39" cy="41" r="3" fill="#FFFFFF" opacity=".42" />
              <path
                d="M29 25c6-9 13-13 21-11"
                fill="none"
                stroke="#fff"
                strokeWidth="3"
                strokeLinecap="round"
                opacity=".72"
              />
            </svg>
            <span className="loading-rocket-flame" />
            <div className="loading-rocket-smoke">
              <i />
              <i />
              <i />
            </div>
          </div>
        </div>
        <p>Taking you to log in…</p>
        <div className="login-loading-progress" aria-hidden="true">
          <span />
        </div>
      </div>
    </main>
  )
}

function AuthSeal({ large = false }: { large?: boolean }) {
  return (
    <span className={large ? "auth-seal auth-seal-large" : "auth-seal"}>
      <span>
        <Icon name="shield" size={large ? 33 : 20} stroke={1.7} />
      </span>
    </span>
  )
}

function Login({
  go,
  initialRole,
}: {
  go: (page: Page, loginRole?: LoginRole) => void
  initialRole: LoginRole
}) {
  const [role, setRole] = useState<LoginRole>(initialRole)
  const [showPassword, setShowPassword] = useState(false)
  const isStudentLogin = role === "Student"
  const destinations: Record<LoginRole, Page> = {
    Student: "my-exams",
    Organizer: "manage-exams",
    Proctor: "exam-monitoring",
    Admin: "admin-dashboard",
  }
  const people = [
    {
      name: "Daniel",
      image:
        "https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=700&q=85",
    },
    {
      name: "Maya",
      image:
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=700&q=85",
    },
    {
      name: "Alex",
      image:
        "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=700&q=85",
    },
    {
      name: "Sarah",
      image:
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=700&q=85",
    },
  ]

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    go(destinations[role])
  }

  return (
    <main className="reference-login">
      <section className="auth-story">
        <div className="auth-watermark">
          <AuthSeal large />
        </div>
        <button className="auth-wordmark" onClick={() => go("beranda")}>
          <AuthSeal />
          <span>
            <strong>EDUAI</strong>
            <small>SMART EXAM INTEGRITY</small>
          </span>
        </button>
        <p>
          EduAI monitors online exams in real time using computer vision,
          helping schools protect academic integrity without disrupting student
          focus.
        </p>
        <div className="video-call-image" aria-label="Four-person video call">
          {people.map((person, index) => (
            <div key={person.name}>
              <img src={person.image} alt={`${person.name} on a video call`} />
              <span>{person.name}</span>
              {index === 3 && <i />}
            </div>
          ))}
          <div className="video-call-toolbar">
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-form" onSubmit={submit}>
          <AuthSeal large />
          <h1>{isStudentLogin ? "Student log in" : "School staff log in"}</h1>
          <p>
            {isStudentLogin
              ? "Log in to start your exam."
              : "Log in to manage or supervise exams."}
          </p>

          {!isStudentLogin && (
            <div
              className="auth-role-tabs"
              role="tablist"
              aria-label="Select staff role"
            >
              {(["Organizer", "Proctor", "Admin"] as LoginRole[]).map(
                (item) => (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={role === item}
                    className={role === item ? "active" : ""}
                    onClick={() => setRole(item)}
                    key={item}
                  >
                    {item}
                  </button>
                ),
              )}
            </div>
          )}

          <label>
            Campus email
            <input type="email" placeholder="e.g. name@campus.ac.id" required />
          </label>
          <label>
            <span>
              Password
              <button type="button">Forgot password?</button>
            </span>
            <div className="auth-password">
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          <button className="auth-submit" type="submit">
            LOG IN
          </button>

          <p className="auth-signup">
            Don&apos;t have an account? <a href="#signup">Register</a>
          </p>
          <button
            className="auth-version-switch"
            type="button"
            onClick={() => setRole(isStudentLogin ? "Organizer" : "Student")}
          >
            {isStudentLogin
              ? "School staff? Log in here"
              : "Student? Log in here"}
          </button>
          <p className="auth-legal">English · © 2026 EduAI</p>
        </form>
      </section>
    </main>
  )
}

function RoleDestination({
  title,
  role,
  go,
}: {
  title: string
  role: LoginRole
  go: (page: Page, loginRole?: LoginRole) => void
}) {
  return (
    <div className="role-destination">
      <header>
        <button onClick={() => go("beranda")} className="destination-brand">
          <AuthSeal />
          <span>EduAI</span>
        </button>
        <nav>
          <span>{role}</span>
          <button onClick={() => go("masuk", role)}>Log out</button>
        </nav>
      </header>
      <main>
        <span className="destination-kicker">{role} workspace</span>
        <h1>{title}</h1>
        <div className="destination-empty">
          <Icon name="file" size={28} />
          <p>This workspace is ready for the next prototype step.</p>
        </div>
      </main>
    </div>
  )
}

function ProctorPortalDashboard({ go }: { go: (page: Page) => void }) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const navigation: [IconName, string, Page | null][] = [
    ["home", "Dashboard", "exam-monitoring"],
    ["calendar", "Exam Sessions", "exam-sessions"],
    ["eye", "Monitoring", "live-monitoring"],
    ["review", "Indications", null],
    ["clock", "History", null],
    ["chart", "Reports", null],
    ["camera", "Video Meeting", null],
    ["users", "Profile", null],
  ]
  const stats = [
    ["8", "Active sessions"],
    ["0", "Students in exam"],
    ["11", "Cases not reviewed"],
    ["20", "Valid detections"],
    ["0", "Needs further review"],
  ]
  const sessions = [
    {
      exam: "Mathematics — Final Assessment",
      className: "Grade 12 · Science 1",
      time: "13:00–14:30",
      present: 34,
      late: 1,
      indications: 6,
      remaining: "42 min",
    },
    {
      exam: "English Language — Semester Test",
      className: "Grade 11 · Social 2",
      time: "13:15–14:45",
      present: 32,
      late: 0,
      indications: 3,
      remaining: "56 min",
    },
    {
      exam: "Physics — Final Assessment",
      className: "Grade 12 · Science 3",
      time: "13:30–15:00",
      present: 30,
      late: 2,
      indications: 2,
      remaining: "1 hr 12 min",
    },
  ]
  const indications = [
    {
      icon: "users" as IconName,
      text: "More than one person seen — 8 times",
      student: "Nadia Permata",
      ago: "2 min ago",
    },
    {
      icon: "phone" as IconName,
      text: "Phone detected in camera view",
      student: "Rizky Ananda",
      ago: "7 min ago",
    },
    {
      icon: "eye" as IconName,
      text: "Looking away repeatedly — 5 times",
      student: "Farhan Akbar",
      ago: "11 min ago",
    },
  ]

  return (
    <div className="proctor-portal">
      <aside className="proctor-sidebar">
        <div className="proctor-logo">
          <Brand inverse />
        </div>
        <nav aria-label="Proctor navigation">
          {navigation.map(([icon, label, destination], index) => (
            <button
              className={index === 0 ? "active" : ""}
              key={label}
              onClick={() => destination && go(destination)}
            >
              <Icon name={icon} size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="proctor-profile">
          <span className="proctor-avatar">RS</span>
          <div>
            <strong>Rina Setiawati</strong>
            <small>Proctor</small>
          </div>
          <button aria-label="Log out" onClick={() => go("masuk")}>
            <Icon name="logout" size={17} />
          </button>
        </div>
      </aside>

      <div className="proctor-main">
        <header className="proctor-topbar">
          <div>
            <h1>Dashboard</h1>
            <p>SMA Negeri 8 Bandung</p>
          </div>
          <div className="proctor-top-actions">
            <span className="live-clock">
              <Icon name="clock" size={16} />
              {now.toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <button className="notification-button" aria-label="Notifications">
              <Icon name="bell" size={20} />
              <i />
            </button>
            <span className="top-avatar">RS</span>
          </div>
        </header>

        <main className="proctor-content">
          <section className="proctor-greeting">
            <div>
              <h2>Good afternoon, Rina</h2>
              <p>Summary of exams assigned to you today.</p>
            </div>
            <span>
              {now.toLocaleDateString("en-GB", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
          </section>

          <section className="proctor-stats" aria-label="Exam statistics">
            {stats.map(([value, label], index) => (
              <article key={label}>
                <strong className={index === 2 ? "gold-number" : ""}>
                  {value}
                </strong>
                <p>{label}</p>
              </article>
            ))}
          </section>

          <div className="proctor-dashboard-grid">
            <section className="proctor-panel active-sessions-panel">
              <div className="proctor-panel-heading">
                <div>
                  <h3>Active sessions</h3>
                  <p>Exams currently assigned to you</p>
                </div>
                <button>View all</button>
              </div>
              <div className="session-list">
                {sessions.map((session) => (
                  <article className="session-card" key={session.exam}>
                    <div className="session-main">
                      <span className="progress-pill">
                        <i />
                        In progress
                      </span>
                      <h4>{session.exam}</h4>
                      <p>
                        {session.className}
                        <span />
                        {session.time}
                      </p>
                      <div className="session-counts">
                        <span>
                          <b>{session.present}</b> Present
                        </span>
                        <span>
                          <b>{session.late}</b> Late
                        </span>
                        <span>
                          <b>{session.indications}</b> Indications
                        </span>
                      </div>
                    </div>
                    <div className="session-action">
                      <small>Remaining time</small>
                      <strong>{session.remaining}</strong>
                      <button>
                        Open monitoring <Icon name="arrow" size={15} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <div className="proctor-right-column">
              <section className="proctor-panel indications-panel">
                <div className="proctor-panel-heading">
                  <div>
                    <h3>Latest indications</h3>
                    <p>Recent activity requiring attention</p>
                  </div>
                  <button>Review all</button>
                </div>
                <div className="indication-list">
                  {indications.map((item) => (
                    <article key={item.text}>
                      <span className="indication-icon">
                        <Icon name={item.icon} size={18} />
                      </span>
                      <div>
                        <strong>{item.text}</strong>
                        <p>
                          {item.student}
                          <span>{item.ago}</span>
                        </p>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="proctor-panel upcoming-panel">
                <div className="proctor-panel-heading">
                  <div>
                    <h3>Upcoming exams</h3>
                    <p>Later today</p>
                  </div>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Exam</th>
                      <th>Class</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>15:30</td>
                      <td>Biology</td>
                      <td>XII Science 2</td>
                    </tr>
                    <tr>
                      <td>16:00</td>
                      <td>Economics</td>
                      <td>XI Social 1</td>
                    </tr>
                  </tbody>
                </table>
              </section>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

function ProctorSubpageShell({
  active,
  title,
  go,
  children,
}: {
  active: "Exam Sessions" | "Monitoring"
  title: string
  go: (page: Page) => void
  children: ReactNode
}) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const navigation: [IconName, string, Page | null][] = [
    ["home", "Dashboard", "exam-monitoring"],
    ["calendar", "Exam Sessions", "exam-sessions"],
    ["eye", "Monitoring", "live-monitoring"],
    ["review", "Indications", null],
    ["clock", "History", null],
    ["chart", "Reports", null],
    ["camera", "Video Meeting", null],
    ["users", "Profile", null],
  ]

  return (
    <div className="proctor-portal">
      <aside className="proctor-sidebar">
        <div className="proctor-logo">
          <Brand inverse />
        </div>
        <nav aria-label="Proctor navigation">
          {navigation.map(([icon, label, destination]) => (
            <button
              className={active === label ? "active" : ""}
              key={label}
              onClick={() => destination && go(destination)}
            >
              <Icon name={icon} size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="proctor-profile">
          <span className="proctor-avatar">RS</span>
          <div>
            <strong>Rina Setiawati</strong>
            <small>Proctor</small>
          </div>
          <button aria-label="Log out" onClick={() => go("masuk")}>
            <Icon name="logout" size={17} />
          </button>
        </div>
      </aside>
      <div className="proctor-main">
        <header className="proctor-topbar">
          <div>
            <h1>{title}</h1>
            <p>SMA Negeri 8 Bandung</p>
          </div>
          <div className="proctor-top-actions">
            <span className="live-clock">
              <Icon name="clock" size={16} />
              {now.toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <button className="notification-button" aria-label="Notifications">
              <Icon name="bell" size={20} />
              <i />
            </button>
            <span className="top-avatar">RS</span>
          </div>
        </header>
        {children}
      </div>
    </div>
  )
}

function ExamSessionsPage({ go }: { go: (page: Page) => void }) {
  const [query, setQuery] = useState("")
  const [status, setStatus] = useState("All statuses")
  const sessions = [
    {
      exam: "Mathematics — Final Assessment",
      date: "18 Feb 2026 · 13:00",
      duration: "90 min",
      participants: "34 / 36",
      proctor: "Rina Setiawati",
      status: "In progress",
    },
    {
      exam: "English Language — Semester Test",
      date: "18 Feb 2026 · 13:15",
      duration: "90 min",
      participants: "32 / 32",
      proctor: "Rina Setiawati",
      status: "In progress",
    },
    {
      exam: "Physics — Final Assessment",
      date: "18 Feb 2026 · 13:30",
      duration: "90 min",
      participants: "30 / 32",
      proctor: "Rina Setiawati",
      status: "In progress",
    },
    {
      exam: "Biology — Practical Theory",
      date: "18 Feb 2026 · 15:30",
      duration: "75 min",
      participants: "0 / 30",
      proctor: "Rina Setiawati",
      status: "Draft",
    },
    {
      exam: "Indonesian Language — Midterm",
      date: "17 Feb 2026 · 09:00",
      duration: "120 min",
      participants: "35 / 35",
      proctor: "Dimas Prabowo",
      status: "Finished",
    },
    {
      exam: "Chemistry — Final Assessment",
      date: "16 Feb 2026 · 10:30",
      duration: "90 min",
      participants: "31 / 31",
      proctor: "Rina Setiawati",
      status: "Finished",
    },
  ]
  const filteredSessions = sessions.filter(
    (session) =>
      session.exam.toLowerCase().includes(query.toLowerCase()) &&
      (status === "All statuses" || session.status === status),
  )

  return (
    <ProctorSubpageShell active="Exam Sessions" title="Exam Sessions" go={go}>
      <main className="proctor-subpage-content">
        <div className="subpage-intro">
          <div>
            <h2>Exam sessions</h2>
            <p>Browse and manage all exam sessions assigned to your school.</p>
          </div>
          <span>{filteredSessions.length} sessions</span>
        </div>
        <div className="session-toolbar">
          <label className="portal-search">
            <Icon name="search" size={17} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search exam name"
            />
          </label>
          <label className="portal-select">
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option>All statuses</option>
              <option>In progress</option>
              <option>Draft</option>
              <option>Finished</option>
            </select>
          </label>
        </div>
        <section className="sessions-table-panel">
          <table>
            <thead>
              <tr>
                <th>Exam name</th>
                <th>Date &amp; time</th>
                <th>Duration</th>
                <th>Participants</th>
                <th>Proctor</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.map((session) => (
                <tr key={`${session.exam}-${session.date}`}>
                  <td>
                    <strong>{session.exam}</strong>
                  </td>
                  <td>{session.date}</td>
                  <td>{session.duration}</td>
                  <td>{session.participants}</td>
                  <td>{session.proctor}</td>
                  <td>
                    <span
                      className={`session-status status-${session.status
                        .toLowerCase()
                        .replace(" ", "-")}`}
                    >
                      {session.status}
                    </span>
                  </td>
                  <td>
                    <button>View details</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredSessions.length === 0 && (
            <div className="table-empty">
              No exam sessions match your search.
            </div>
          )}
        </section>
      </main>
    </ProctorSubpageShell>
  )
}

function LiveMonitoringPage({ go }: { go: (page: Page) => void }) {
  const [view, setView] = useState<"Summary" | "Grid">("Grid")
  const [source, setSource] = useState("Browser")
  const [aiRunning, setAiRunning] = useState(false)
  const [filter, setFilter] = useState("All")
  const [query, setQuery] = useState("")
  const students = [
    {
      name: "Alya Pratama",
      id: "STU-24018",
      status: "Normal",
      indication: "No recent indication",
      image: "/images/ai-signals/1_phone_in_view.png",
    },
    {
      name: "Rizky Ananda",
      id: "STU-24024",
      status: "Needs attention",
      indication: "Phone in view",
      image: "/images/ai-signals/2_book_in_view.png",
    },
    {
      name: "Nadia Permata",
      id: "STU-24031",
      status: "Needs attention",
      indication: "Another person seen",
      image: "/images/ai-signals/3_another_person.png",
    },
    {
      name: "Farhan Akbar",
      id: "STU-24037",
      status: "Normal",
      indication: "Looking away · 2 min ago",
      image: "/images/ai-signals/4_looking_away.png",
    },
    {
      name: "Salsa Rahma",
      id: "STU-24042",
      status: "Cannot analyse",
      indication: "Camera too dark",
      image: "/images/ai-signals/5_face_not_visible.png",
    },
    {
      name: "Dito Nugraha",
      id: "STU-24045",
      status: "Offline",
      indication: "Connection lost",
      image: "/images/ai-signals/6_other_voice.png",
    },
  ]
  const tabs = [
    "All",
    "Normal",
    "Needs attention",
    "Cannot analyse",
    "Connection issue",
  ]
  const filteredStudents = students.filter((student) => {
    const matchesStatus =
      filter === "All" ||
      student.status === filter ||
      (filter === "Connection issue" && student.status === "Offline")
    return (
      matchesStatus &&
      `${student.name} ${student.id}`
        .toLowerCase()
        .includes(query.toLowerCase())
    )
  })

  return (
    <ProctorSubpageShell active="Monitoring" title="Monitoring" go={go}>
      <main className="monitoring-content">
        <section className="monitoring-controls">
          <label>
            <span>Exam</span>
            <select>
              <option>SEB exam — In progress</option>
              <option>Mathematics — In progress</option>
            </select>
          </label>
          <div className="view-toggle" aria-label="View mode">
            {(["Summary", "Grid"] as const).map((item) => (
              <button
                className={view === item ? "active" : ""}
                onClick={() => setView(item)}
                key={item}
              >
                {item}
              </button>
            ))}
          </div>
          <label>
            <span>Video source</span>
            <select
              value={source}
              onChange={(event) => setSource(event.target.value)}
            >
              <option>Browser</option>
              <option>OpenVidu</option>
              <option>Jitsi</option>
            </select>
          </label>
          <button
            className={aiRunning ? "start-ai active" : "start-ai"}
            onClick={() => setAiRunning(!aiRunning)}
          >
            {aiRunning ? "AI running" : "Start AI"}
          </button>
        </section>

        <div className="security-notice">
          <Icon name="shield" size={18} />
          <strong>Exam security:</strong>
          Safe Exam Browser required — 0/1 students verified.
        </div>

        <section className="monitoring-stats">
          {[
            ["6", "Total students"],
            ["5", "Online"],
            ["2", "Needs attention"],
            ["14", "Indications recorded"],
          ].map(([value, label]) => (
            <article key={label}>
              <strong>{value}</strong>
              <p>{label}</p>
            </article>
          ))}
        </section>

        <section className="monitoring-filterbar">
          <div className="monitoring-tabs">
            {tabs.map((item) => (
              <button
                className={filter === item ? "active" : ""}
                onClick={() => setFilter(item)}
                key={item}
              >
                {item}
              </button>
            ))}
          </div>
          <label className="portal-search">
            <Icon name="search" size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search student"
            />
          </label>
        </section>

        <div className="monitoring-workspace">
          <section
            className={`student-video-grid ${
              view === "Summary" ? "summary-view" : ""
            }`}
          >
            {filteredStudents.map((student) => (
              <article className="student-tile" key={student.id}>
                <div className="student-video">
                  <img
                    src={student.image}
                    alt={`${student.name} live camera`}
                  />
                  <span
                    className={`student-state state-${student.status
                      .toLowerCase()
                      .replace(" ", "-")}`}
                  >
                    {student.status}
                  </span>
                  <small>{student.indication}</small>
                </div>
                <div className="student-tile-footer">
                  <div>
                    <strong>{student.name}</strong>
                    <span>{student.id}</span>
                  </div>
                  <button>Open monitoring</button>
                </div>
              </article>
            ))}
            {filteredStudents.length === 0 && (
              <div className="monitoring-empty">
                No students match this filter.
              </div>
            )}
          </section>

          <aside className="activity-sidebar">
            <section className="proctor-panel activity-feed">
              <div className="proctor-panel-heading">
                <div>
                  <h3>Recent activity</h3>
                  <p>Live events from this exam</p>
                </div>
              </div>
              {[
                ["Phone detected", "Rizky Ananda", "1 min"],
                ["Second face appeared", "Nadia Permata", "3 min"],
                ["Camera quality dropped", "Salsa Rahma", "5 min"],
                ["Student reconnected", "Dito Nugraha", "8 min"],
              ].map(([event, student, time]) => (
                <article key={`${event}-${student}`}>
                  <i />
                  <div>
                    <strong>{event}</strong>
                    <p>{student}</p>
                  </div>
                  <span>{time}</span>
                </article>
              ))}
            </section>
            <section className="human-review-box">
              <Icon name="users" size={22} />
              <div>
                <strong>Human review needed</strong>
                <p>
                  AI only helps highlight possible events; it does not decide
                  whether a student cheated.
                </p>
              </div>
            </section>
          </aside>
        </div>
      </main>
    </ProctorSubpageShell>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>("beranda")
  const [loginRole, setLoginRole] = useState<LoginRole>("Student")
  const go = (next: Page, nextLoginRole?: LoginRole) => {
    if (next === "masuk" && nextLoginRole) setLoginRole(nextLoginRole)
    setPage(next)
    window.scrollTo(0, 0)
  }
  const startLoginLoading = (role: LoginRole) => {
    setLoginRole(role)
    setPage("loading")
    window.scrollTo(0, 0)
  }
  if (page === "loading")
    return <LoginLoadingScreen onComplete={() => setPage("masuk")} />
  if (page === "masuk") return <Login go={go} initialRole={loginRole} />
  if (page === "my-exams")
    return <RoleDestination title="My Exams" role="Student" go={go} />
  if (page === "manage-exams")
    return <RoleDestination title="Manage Exams" role="Organizer" go={go} />
  if (page === "exam-monitoring") return <ProctorPortalDashboard go={go} />
  if (page === "exam-sessions") return <ExamSessionsPage go={go} />
  if (page === "live-monitoring") return <LiveMonitoringPage go={go} />
  if (page === "admin-dashboard")
    return <RoleDestination title="Admin Dashboard" role="Admin" go={go} />
  if (page === "siswa") return <StudentDashboard go={go} />
  if (page === "pengawas") return <ProctorDashboard go={go} />
  if (page === "admin") return <AdminDashboard go={go} />
  if (page === "sistem") return <DesignSystem go={go} />
  return <Landing go={go} startLoginLoading={startLoginLoading} />
}
