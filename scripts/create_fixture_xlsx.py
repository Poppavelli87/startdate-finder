from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures" / "businesses_fixture.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    headers = [
        "Business ID",
        "Business",
        "TOB",
        "Mailing Address 1",
        "City",
        "State",
        "Zip",
        "County",
        "Phone",
        "Contact",
        "URL",
        "Date Established",
    ]
    sheet.append(headers)
    sheet.append(
        [
            "BIZ-001",
            "Acme Plumbing LLC",
            "Plumbing",
            "123 Main St",
            "Hartford",
            "CT",
            "06103",
            "Hartford",
            "555-1010",
            "Jane Doe",
            "https://acmeplumbing.com",
            "",
        ]
    )
    sheet.append(
        [
            "BIZ-002",
            "Smith Services LLC",
            "General Contractor",
            "44 Elm St",
            "New Haven",
            "CT",
            "06510",
            "New Haven",
            "555-2020",
            "John Smith",
            "https://smith-services.example",
            "",
        ]
    )
    workbook.save(output)
    print(f"Wrote fixture: {output}")


if __name__ == "__main__":
    main()

