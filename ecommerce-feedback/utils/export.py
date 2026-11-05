"""Helpers for files that users download."""


def safe_csv_cell(value):
    """Stop spreadsheet apps running a cell as a formula. Review text comes from
    customers, so a cell starting with = + - or @ could otherwise run in Excel."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value
