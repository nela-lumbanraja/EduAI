"""Report exports. The PDF follows the school template "Laporan Hasil Pengawasan Ujian"."""
import io
from datetime import datetime
from pathlib import Path
from typing import Dict
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (HRFlowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from . import summary
from .report import AI_NOTICE, RETENTION_TEXT, local

SEAL = Path(__file__).parent / "assets" / "eduai-seal.png"
TITLE = "Laporan Hasil Pengawasan Ujian"
TEMPLATE_NOTICE = "Catatan sistem hanya menunjukkan hal yang perlu diperiksa. Keputusan ada pada pengawas setelah melihat rekaman dan konteksnya."
NAVY = colors.HexColor("#0a2547")
LINE = colors.HexColor("#e4e1d6")
HEAD = colors.HexColor("#f3f1ec")
GREY = colors.HexColor("#5f6470")
DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
          "November", "Desember"]
DOTS = "." * 104

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=6, alignment=TA_LEFT)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9.5, leading=12.5, spaceAfter=0)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, textColor=GREY)
H1 = ParagraphStyle("h1", fontName="Times-Roman", fontSize=23, leading=28, spaceBefore=6, spaceAfter=10)
H2 = ParagraphStyle("h2", fontName="Times-Roman", fontSize=15.5, leading=20, spaceBefore=14, spaceAfter=8, keepWithNext=1)


def _p(text, style=BODY):
    return Paragraph(escape("" if text is None else str(text)), style)


def _table(rows, widths, header=True):
    body = [[c if not isinstance(c, str) else _p(c, CELL_HEAD if header and i == 0 else CELL) for c in row]
            for i, row in enumerate(rows)]
    t = Table(body, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.7, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD))
    t.setStyle(TableStyle(style))
    return t


class _NumberedCanvas(pdf_canvas.Canvas):
    """Two passes so the footer can say "Halaman x dari y"; adds the DRAF mark to every page."""
    draft = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for i, state in enumerate(self._pages, 1):
            self.__dict__.update(state)
            w, h = A4
            self.setFont("Helvetica", 7.5)
            self.setFillColor(GREY)
            self.drawString(18 * mm, h - 11 * mm, TITLE)
            self.drawRightString(w - 18 * mm, 11 * mm, f"Halaman {i} dari {total}")
            if self.draft:
                self.saveState()
                self.setFont("Helvetica-Bold", 90)
                self.setFillColor(colors.Color(0.75, 0.75, 0.78, alpha=0.28))
                self.translate(w / 2, h / 2)
                self.rotate(45)
                self.drawCentredString(0, -30, "DRAF")
                self.restoreState()
            super().showPage()
        super().save()


def _picture(data):
    """A flowable, or None when the bytes cannot be read as an image."""
    try:
        iw, ih = ImageReader(io.BytesIO(data)).getSize()
    except Exception:
        return None
    w = 68.0
    return Image(io.BytesIO(data), width=w, height=w * ih / iw)


def _date_id(exam) -> str:
    d = datetime.strptime(exam["date"], "%Y-%m-%d")
    return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]} {d.year}"


def _clock(dt) -> str:
    return dt.strftime("%H.%M")


def event_label(e) -> str:
    return e.get("label") or e["indicator"]


def image_note(e, data: dict) -> str:
    state = e["evidence"]["state"]
    if state == "deleted":
        return RETENTION_TEXT
    if state == "none":
        return "Tidak ada gambar"
    return "Gambar tidak dapat dibaca" if data["can_view_evidence"] else data["restricted_text"]


def build_pdf(data: dict, frames: Dict[str, bytes], settings) -> bytes:
    exam, att, ind, events = data["exam"], data["attendance"], data["indications"], data["events"]
    final, tz = data["final"], settings.exam_timezone
    win = summary.exam_window(exam, tz)
    start, end = (_clock(win[0]), _clock(win[1])) if win else ("........", "........")
    time_of = lambda iso: (local(iso, tz).strftime("%H.%M.%S") if iso else "")   # noqa: E731
    supervisor = (exam.get("supervisor") or {}).get("name") or ""

    kop = [f"<b>{escape(settings.school_name or '[NAMA SEKOLAH]')}</b>", escape(settings.school_address or "[Alamat sekolah]"),
           f"· Telp. {escape(settings.school_phone or '[.........]')}", f"· {escape(settings.school_email or '[email sekolah]')}"]
    brand = Table([[Image(str(SEAL), width=62, height=62),
                    [Paragraph("EduAI", ParagraphStyle("b", fontName="Times-Bold", fontSize=26, leading=30, textColor=NAVY)),
                     Paragraph("PENGAWASAN UJIAN", ParagraphStyle("t", fontName="Helvetica", fontSize=9, leading=13, textColor=GREY))]]],
                  colWidths=[74, 300], hAlign="LEFT")
    brand.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    s = [brand, Spacer(1, 8), Paragraph(" ".join(kop), BODY), HRFlowable(width="100%", thickness=0.7, color=GREY, spaceAfter=6),
         _p(TITLE, H1), _p("Nomor: ......../......../20...."), _p("Lampiran: ...... lembar"), _p(f"Perihal: {TITLE}"),
         _p("I. Identitas Ujian", H2),
         _table([["Keterangan", "Isian"], ["Nama ujian", exam["name"]], ["Mata pelajaran", exam.get("subject") or ""],
                 ["Kelas", exam.get("class_name") or ""], ["Hari, tanggal", _date_id(exam)],
                 ["Waktu", f"{start} s.d. {end} WIB ({exam['duration_min']} menit)"],
                 ["Bentuk ujian", "Daring, diawasi melalui EduAI"], ["Pengawas", supervisor]], [110, 300]),
         PageBreak(),
         _p("II. Kehadiran Peserta", H2),
         _table([["Keterangan", "Jumlah"], ["Peserta terdaftar", f"{att['enrolled']} orang"], ["Hadir mengikuti ujian", f"{att['joined']} orang"],
                 ["Tidak hadir", f"{att['not_joined']} orang"]], [150, 80]),
         Spacer(1, 8), _p("Nama peserta yang tidak hadir beserta alasannya (jika ada):")]
    absent = data.get("absent") or []
    s += [_p(f"{i}. {a} ........................", BODY) for i, a in enumerate(absent, 1)] or [_p("1. " + "." * 40), _p("2. " + "." * 40)]
    s += [_p("III. Jalannya Ujian", H2),
          _p(f"Ujian dimulai pukul {start} WIB dan berakhir pukul {end} WIB. Secara umum ujian berjalan [lancar / ada kendala]."),
          _p("Kendala yang terjadi selama ujian (koneksi, kamera, mikrofon, atau lainnya):"), _p(DOTS), _p(DOTS),
          _p("IV. Catatan Pemantauan", H2)]
    reviewed = "Setiap kejadian sudah ditinjau oleh pengawas dengan hasil sebagai berikut." if final else (
        f"Dokumen ini masih draf: {ind['unreviewed']} kejadian belum ditinjau pengawas.")
    s.append(_p(f"Selama ujian, sistem pemantauan mencatat {ind['total']} kejadian yang perlu diperiksa. {reviewed}"))
    rows = [["No", "Nama peserta", "Waktu", "Kejadian yang tercatat", "Hasil peninjauan pengawas", "Keterangan"]]
    rows += [[str(i), (e.get("student") or {}).get("name") or "", time_of(e["start_ts"]), event_label(e),
              e.get("review_status") or "Belum ditinjau", (e.get("last_review") or {}).get("note") or ""]
             for i, e in enumerate(events, 1)]
    if not events:
        rows.append(["—", "Tidak ada kejadian tercatat", "", "", "", ""])
    s += [_table(rows, [30, 92, 50, 100, 92, 100]), Spacer(1, 8),
          _p("Hasil peninjauan diisi salah satu: Valid, Tidak Valid, atau Perlu Tinjauan Lanjut."), _p(TEMPLATE_NOTICE), PageBreak(),
          _p(f"Waktu video tidak dapat dianalisis (gelap, buram, atau kamera mati): {ind['cannot_analyze']} kali, "
             f"total sekitar {round(ind.get('cannot_analyze_s', 0) / 60)} menit."),
          _p("V. Tindak Lanjut", H2), _p(DOTS), _p(DOTS),
          _p("Demikian laporan ini dibuat dengan sebenarnya untuk dapat dipergunakan sebagaimana mestinya."),
          _p(f"{settings.school_city or '[Kota]'}, .................... 20...."),
          KeepTogether(_table([["Mengetahui,", ""], ["Kepala Sekolah", "Pengawas Ujian"], [Spacer(1, 38), Spacer(1, 38)],
                               ["( .............................. )", f"( {supervisor or '..............................'} )"],
                               ["NIP. ........................", "NIP. ........................"]], [140, 140])),
          Spacer(1, 10), HRFlowable(width="100%", thickness=0.7, color=GREY, spaceAfter=6),
          _p("Lampiran: Gambar Bukti Pemantauan", H2),
          _p("Gambar diambil dari EduAI, menu Indikasi, tombol Lihat Evidence pada kejadian yang ditinjau. "
             "Satu baris untuk satu kejadian pada tabel IV.")]
    rows = [["No", "Nama peserta", "Waktu", "Gambar", "Keterangan"]]
    for i, e in enumerate(events, 1):
        pic = _picture(frames[e["event_id"]]) if e["event_id"] in frames else None
        note = (e.get("last_review") or {}).get("note") or ""
        rows.append([str(i), (e.get("student") or {}).get("name") or "", time_of(e["start_ts"]), pic or image_note(e, data), note])
    if not events:
        rows.append(["—", "Tidak ada kejadian tercatat", "", "", ""])
    s += [_table(rows, [30, 108, 54, 92, 146]), Spacer(1, 8),
          _p("Gambar bukti hanya untuk keperluan peninjauan dan tidak disebarluaskan.")]

    out = io.BytesIO()
    canvas_cls = type("ReportCanvas", (_NumberedCanvas,), {"draft": not final})
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"{TITLE} - {exam['name']}", author="EduAI")
    doc.build(s, canvasmaker=canvas_cls)
    return out.getvalue()


def build_xlsx(data: dict, settings) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Indikasi"
    head = ["No", "Nama peserta", "NIS", "Kejadian yang tercatat", "Mulai", "Selesai", "Hasil peninjauan pengawas",
            "Catatan pengawas", "Peninjau", "Gambar bukti"]
    ws.append(head)
    tz = settings.exam_timezone
    stamp = lambda iso: (local(iso, tz).strftime("%Y-%m-%d %H:%M:%S") if iso else "")   # noqa: E731
    state = {"available": "Tersedia di EduAI" if data["can_view_evidence"] else data["restricted_text"],
             "deleted": RETENTION_TEXT, "none": "Tidak ada gambar"}
    for i, e in enumerate(data["events"], 1):
        stu, rev = e.get("student") or {}, e.get("last_review") or {}
        row = [i, stu.get("name"), stu.get("nis"), event_label(e), stamp(e["start_ts"]), stamp(e.get("end_ts")),
               e.get("review_status") or "Belum ditinjau", rev.get("note"), rev.get("reviewer"), state[e["evidence"]["state"]]]
        ws.append(row)
        for cell in ws[ws.max_row][1:]:         # text stays text: a note starting with "=" must never run as a formula
            if cell.value is not None:
                cell.value = str(cell.value)
                cell.data_type = "s"
                cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="F3F1EC")
    for col, width in zip("ABCDEFGHIJ", (5, 26, 12, 28, 20, 20, 24, 36, 20, 28)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    note = wb.create_sheet("Catatan")
    for line in (data["exam"]["name"], "Status laporan: " + ("Final" if data["final"] else "Draf"), AI_NOTICE):
        note.append([line])
    note.column_dimensions["A"].width = 100
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
