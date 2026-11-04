"""Local SVG icons embedded as images supported by Streamlit's HTML sanitizer."""
from base64 import b64encode

_SHAPES = {
    "portal": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 17.5h7m-3.5-3.5v7"/>',
    "kasir": '<path d="M3 8h18v13H3zM2 3h20v5H2zM9 12h6"/>',
    "pasien": '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M12 11v6M9 14h6"/>',
    "browser_stack": '<path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    "antrean": '<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 4v3"/>',
    "hotel": '<path d="M5 21V3h14v18M3 21h18M9 21v-5h6v5M9 7h1M14 7h1M9 11h1M14 11h1"/>',
}


def app_icon(slug: str) -> str:
    color = "#ffffff" if slug == "portal" else "#2563eb"
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="1.7" '
            'stroke-linecap="round" stroke-linejoin="round" focusable="false">'
            + _SHAPES[slug] + '</svg>')
    svg = svg.replace('currentColor', color)
    encoded = b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{encoded}" alt="" width="24" height="24" aria-hidden="true">'
