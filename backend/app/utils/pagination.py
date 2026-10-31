def pagination_meta(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}
