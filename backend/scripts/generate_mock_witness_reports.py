from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 54
RIGHT_MARGIN = 54
TOP_MARGIN = 54
BOTTOM_MARGIN = 54
BODY_FONT_SIZE = 11
BODY_LINE_HEIGHT = 15
SMALL_FONT_SIZE = 9
SMALL_LINE_HEIGHT = 12
HEADING_FONT_SIZE = 13
HEADING_LINE_HEIGHT = 18
TITLE_FONT_SIZE = 18
TITLE_LINE_HEIGHT = 24
SUBTITLE_FONT_SIZE = 10
SUBTITLE_LINE_HEIGHT = 14
BODY_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


@dataclass
class TextLine:
    x: int
    y: int
    font: str
    size: int
    text: str


class DocumentLayout:
    def __init__(self) -> None:
        self.pages: list[list[TextLine]] = [[]]
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def _new_page(self) -> None:
        self.pages.append([])
        self.cursor_y = PAGE_HEIGHT - TOP_MARGIN

    def _ensure_space(self, required_height: int) -> None:
        if self.cursor_y - required_height < BOTTOM_MARGIN:
            self._new_page()

    def add_spacer(self, height: int = 8) -> None:
        self._ensure_space(height)
        self.cursor_y -= height

    def add_line(
        self,
        text: str,
        *,
        font: str = "F1",
        size: int = BODY_FONT_SIZE,
        leading: int = BODY_LINE_HEIGHT,
        indent: int = 0,
    ) -> None:
        self._ensure_space(leading)
        self.pages[-1].append(
            TextLine(
                x=LEFT_MARGIN + indent,
                y=self.cursor_y,
                font=font,
                size=size,
                text=text,
            )
        )
        self.cursor_y -= leading

    def add_wrapped(
        self,
        text: str,
        *,
        font: str = "F1",
        size: int = BODY_FONT_SIZE,
        leading: int = BODY_LINE_HEIGHT,
        indent: int = 0,
        bullet: str | None = None,
    ) -> None:
        available_width = BODY_WIDTH - indent
        max_chars = max(24, int(available_width / (size * 0.54)))
        prefix = bullet or ""
        initial_indent = len(prefix)
        wrapped = textwrap.wrap(
            text,
            width=max_chars,
            break_long_words=False,
            break_on_hyphens=False,
            initial_indent=prefix,
            subsequent_indent=" " * initial_indent,
        )
        for line in wrapped or [prefix]:
            self.add_line(
                line,
                font=font,
                size=size,
                leading=leading,
                indent=indent,
            )


def pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def build_page_stream(
    lines: list[TextLine],
    *,
    page_index: int,
    page_count: int,
) -> bytes:
    commands: list[str] = []
    for line in lines:
        commands.append(
            f"BT /{line.font} {line.size} Tf 1 0 0 1 {line.x} {line.y} Tm ({pdf_escape(line.text)}) Tj ET"
        )

    commands.append("0.4 w 54 34 m 558 34 l S")
    commands.append(
        f"BT /F1 8 Tf 1 0 0 1 54 22 Tm ({pdf_escape('Fictional demo artifact for Clarion sample evidence only.')}) Tj ET"
    )
    commands.append(
        f"BT /F1 8 Tf 1 0 0 1 500 22 Tm ({pdf_escape(f'Page {page_index} of {page_count}')}) Tj ET"
    )
    return "\n".join(commands).encode("latin-1")


def write_pdf(pages: list[list[TextLine]], output_path: Path) -> None:
    objects: list[str | bytes | None] = [None]

    def add_object(content: str | bytes) -> int:
        objects.append(content)
        return len(objects) - 1

    catalog_num = add_object("")
    pages_num = add_object("")
    regular_font_num = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold_font_num = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    page_numbers: list[int] = []
    total_pages = len(pages)
    for index, page_lines in enumerate(pages, start=1):
        stream = build_page_stream(page_lines, page_index=index, page_count=total_pages)
        content_num = add_object(stream)
        page_num = add_object(
            (
                f"<< /Type /Page /Parent {pages_num} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {regular_font_num} 0 R /F2 {bold_font_num} 0 R >> >> "
                f"/Contents {content_num} 0 R >>"
            )
        )
        page_numbers.append(page_num)

    kids = " ".join(f"{page_num} 0 R" for page_num in page_numbers)
    objects[pages_num] = f"<< /Type /Pages /Count {len(page_numbers)} /Kids [{kids}] >>"
    objects[catalog_num] = f"<< /Type /Catalog /Pages {pages_num} 0 R >>"

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for number in range(1, len(objects)):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("latin-1"))
        body = objects[number]
        if isinstance(body, bytes):
            output.extend(f"<< /Length {len(body)} >>\nstream\n".encode("latin-1"))
            output.extend(body)
            output.extend(b"\nendstream\n")
        else:
            output.extend(str(body).encode("latin-1"))
            output.extend(b"\n")
        output.extend(b"endobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects)}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer << /Size {len(objects)} /Root {catalog_num} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
    )
    output_path.write_bytes(output)


def add_metadata_block(layout: DocumentLayout, report: dict, case_info: dict) -> None:
    layout.add_line(
        "WITNESS STATEMENT",
        font="F2",
        size=TITLE_FONT_SIZE,
        leading=TITLE_LINE_HEIGHT,
    )
    layout.add_line(
        "FICTIONAL DEMO DOCUMENT - CREATED FOR CLARION SAMPLE EVIDENCE",
        font="F2",
        size=SUBTITLE_FONT_SIZE,
        leading=SUBTITLE_LINE_HEIGHT,
    )
    layout.add_spacer(10)

    metadata = [
        f"Document ID: {report['document_id']}",
        f"Case Number: {case_info['case_number']}",
        f"Incident Date: {case_info['incident_date']}",
        f"Incident Time: {case_info['incident_time']}",
        f"Incident Location: {case_info['location']}",
    ]
    for line in metadata:
        layout.add_wrapped(line)


def add_section(layout: DocumentLayout, heading: str, paragraphs: list[str]) -> None:
    layout.add_spacer(8)
    layout.add_line(
        heading.upper(),
        font="F2",
        size=HEADING_FONT_SIZE,
        leading=HEADING_LINE_HEIGHT,
    )
    for paragraph in paragraphs:
        layout.add_wrapped(paragraph)
        layout.add_spacer(4)


def build_report_pages(report: dict, case_info: dict) -> list[list[TextLine]]:
    layout = DocumentLayout()
    add_metadata_block(layout, report, case_info)
    layout.add_spacer(8)

    witness = report["witness"]
    statement_taken = report["statement_taken"]
    witness_lines = [
        f"Witness Name: {witness['name']}",
        f"Age: {witness['age']}",
        f"Occupation: {witness['occupation']}",
        f"Address: {witness['address']}",
        f"Phone: {witness['phone']}",
        f"Email: {witness['email']}",
        f"Role: {witness['relationship']}",
        f"Observation Point: {witness['observation_point']}",
    ]
    add_section(layout, "Witness Information", witness_lines)

    statement_lines = [
        f"Statement Date: {statement_taken['date']}",
        f"Statement Time: {statement_taken['time']}",
        f"Taken By: {statement_taken['taken_by']}",
        f"Method: {statement_taken['method']}",
        f"Approximate Duration: {statement_taken['duration']}",
    ]
    add_section(layout, "Statement Intake", statement_lines)

    add_section(layout, "Incident Overview", [case_info["summary"]])
    add_section(layout, "Witness Narrative", report["narrative"])

    layout.add_spacer(8)
    layout.add_line(
        "KEY OBSERVATIONS",
        font="F2",
        size=HEADING_FONT_SIZE,
        leading=HEADING_LINE_HEIGHT,
    )
    for observation in report["observations"]:
        layout.add_wrapped(observation, bullet="- ")
        layout.add_spacer(2)

    add_section(layout, "Post-Impact Account", report["post_impact"])
    add_section(layout, "Attestation", [report["attestation"]])

    signature_lines = [
        f"Witness Signature: /s/ {report['signature_name']}",
        f"Signature Date: {report['signature_date']}",
    ]
    add_section(layout, "Signature", signature_lines)
    return layout.pages


def load_source_data(source_path: Path) -> dict:
    return json.loads(source_path.read_text(encoding="utf-8"))


def generate_reports(source_path: Path, output_dir: Path) -> list[Path]:
    source_data = load_source_data(source_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []
    case_info = source_data["case"]
    for report in source_data["reports"]:
        pages = build_report_pages(report, case_info)
        output_path = output_dir / report["file_name"]
        write_pdf(pages, output_path)
        created_files.append(output_path)
    return created_files


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "mock-evidence" / "witness-reports.json"
    output_dir = repo_root / "mock-evidence"
    created_files = generate_reports(source_path, output_dir)
    for file_path in created_files:
        print(f"Generated {file_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
