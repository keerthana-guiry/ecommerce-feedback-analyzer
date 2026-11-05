"""Reads and checks an uploaded CSV file of reviews. Nothing here touches the database."""

import csv
import io
from datetime import datetime

from utils.validation import review_error

MAX_ROWS = 5000
EARLIEST_YEAR = 2000

# The accepted column names. The app's own CSV export also matches these.
COLUMN_NAMES = {
    "product": "product",
    "product_name": "product",
    "rating": "rating",
    "review": "review_text",
    "review_text": "review_text",
    "customer": "customer_name",
    "customer_name": "customer_name",
    "date": "review_date",
    "review_date": "review_date",
}
REQUIRED_COLUMNS = {"product": "product", "rating": "rating", "review_text": "review"}


class CsvFileError(ValueError):
    """The file as a whole can't be read, so there are no rows to report on."""


def _decode(raw):
    # Excel on Windows often saves CSV files as cp1252 rather than UTF-8
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFileError("This file's text encoding isn't supported. Please save it as CSV UTF-8.")


def _parse_rating(value):
    """Accept whole numbers, including the 5.0 that spreadsheets sometimes write."""
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else None


def _parse_date(value):
    """Returns (date or None, error or None). A blank date means the upload time."""
    if not value:
        return None, None
    try:
        parsed = datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None, "Dates must look like 2026-01-31."
    if parsed > datetime.now():
        return None, "The date is in the future."
    if parsed.year < EARLIEST_YEAR:
        return None, f"The date is before {EARLIEST_YEAR}."
    return parsed, None


def parse_reviews_csv(raw, product_ids):
    """Check every row of an uploaded file. `product_ids` maps lowercase product
    names to their ids. Returns (rows, errors), with one error per invalid row.
    Raises CsvFileError if the file can't be read at all."""
    reader = csv.DictReader(io.StringIO(_decode(raw), newline=""))

    columns = {}
    try:
        for header in reader.fieldnames or []:
            name = COLUMN_NAMES.get(header.strip().lower().replace(" ", "_"))
            if name:
                columns.setdefault(name, header)

        missing = [label for name, label in REQUIRED_COLUMNS.items() if name not in columns]
        if missing:
            raise CsvFileError("The file needs these columns: " + ", ".join(missing) + ".")

        rows = []
        errors = []
        for row in reader:
            if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
                continue
            if len(rows) + len(errors) >= MAX_ROWS:
                raise CsvFileError(f"Files can have at most {MAX_ROWS} reviews.")

            def cell(name):
                return (row[columns[name]] or "").strip() if name in columns else ""

            product_id = product_ids.get(cell("product").lower())
            rating = _parse_rating(cell("rating"))
            review_date, date_error = _parse_date(cell("review_date"))
            error = (f'Unknown product "{cell("product")}".' if not product_id else None) \
                or review_error(rating, cell("review_text"), cell("customer_name")) \
                or date_error

            if error:
                errors.append(f"Row {reader.line_num}: {error}")
            else:
                rows.append({
                    "product_id": product_id,
                    "rating": rating,
                    "review_text": cell("review_text"),
                    "customer_name": cell("customer_name") or None,
                    "review_date": review_date,
                })
    except csv.Error as error:
        raise CsvFileError(f"This file couldn't be read as a CSV: {error}") from error

    if not rows and not errors:
        raise CsvFileError("This file has no reviews in it.")
    return rows, errors
