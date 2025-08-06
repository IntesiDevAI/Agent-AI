"""
rimappa_utils.py
=================

Questo modulo contiene una serie di funzioni di supporto per lavorare con
l'output di Google Document AI. Le funzioni sono progettate per essere
compatibili sia con gli oggetti protobuf restituiti dalla libreria
`google.cloud.documentai_v1` sia con i dizionari Python ottenuti
serializzando gli oggetti (ad esempio tramite ``Document.to_json`` o
``Document.to_dict``).  Raggruppare queste helper in un file separato
permette di riutilizzarle in più moduli ed evita che i linter segnalino
variabili non definite quando vengono utilizzate all'esterno.

Per utilizzarle in un altro modulo (come ``gdocai.py``), è sufficiente
importare le funzioni necessarie, ad esempio:

    from rimappa_utils import (_get_entities, _get_pages, _get_entity_type,
                               _get_entity_mention, _get_entity_properties,
                               _get_property_type, _get_property_mention,
                               _get_document_text, _get_tables,
                               _get_header_rows, _get_body_rows, _get_cells,
                               _get_layout, _get_text_anchor,
                               _get_text_segments, _extract_text_from_segments,
                               _cell_text, _parse_number)

Queste funzioni sono state pensate per supportare la funzione
``rimappa_json``
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union


def _getattr(obj: Any, attr: str, default: Optional[Any] = None) -> Any:
    """Recupera un attributo da un oggetto oppure una chiave da un dizionario.

    Se ``obj`` è ``None``, restituisce ``default``.  Se ``obj`` è un
    dizionario, usa ``obj.get(attr, default)``, altrimenti usa
    ``getattr(obj, attr, default)``.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _get_entities(document: Any) -> Sequence[Any]:
    """Restituisce la sequenza di entità dal documento."""
    return _getattr(document, "entities", []) or []


def _get_pages(document: Any) -> Sequence[Any]:
    """Restituisce la sequenza di pagine dal documento."""
    return _getattr(document, "pages", []) or []


def _get_entity_type(entity: Any) -> str:
    """Restituisce il tipo di entità in minuscolo."""
    return (_getattr(entity, "type_", None) or _getattr(entity, "type", "")).lower()


def _get_entity_mention(entity: Any) -> str:
    """Restituisce il testo associato a un'entità."""
    return (
        _getattr(entity, "mention_text", None)
        or _getattr(entity, "mentionText", "")
        or ""
    ).strip()


def _get_entity_properties(entity: Any) -> Sequence[Any]:
    """Restituisce la sequenza di proprietà di un'entità."""
    return _getattr(entity, "properties", []) or []


def _get_property_type(prop: Any) -> str:
    """Restituisce il tipo di una proprietà in minuscolo."""
    return (_getattr(prop, "type_", None) or _getattr(prop, "type", "")).lower()


def _get_property_mention(prop: Any) -> str:
    """Restituisce il testo associato a una proprietà."""
    return (
        _getattr(prop, "mention_text", None)
        or _getattr(prop, "mentionText", "")
        or ""
    ).strip()


def _get_document_text(document: Any) -> str:
    """Restituisce il testo completo del documento."""
    return _getattr(document, "text", "") or ""


def _get_tables(page: Any) -> Sequence[Any]:
    """Restituisce la sequenza di tabelle presenti in una pagina."""
    return _getattr(page, "tables", []) or []


def _get_header_rows(table: Any) -> Sequence[Any]:
    """Restituisce le righe di intestazione della tabella."""
    return _getattr(table, "header_rows", None) or _getattr(table, "headerRows", []) or []


def _get_body_rows(table: Any) -> Sequence[Any]:
    """Restituisce le righe del corpo della tabella."""
    return _getattr(table, "body_rows", None) or _getattr(table, "bodyRows", []) or []


def _get_cells(row: Any) -> Sequence[Any]:
    """Restituisce le celle di una riga."""
    return _getattr(row, "cells", []) or []


def _get_layout(cell: Any) -> Any:
    """Restituisce il layout di una cella."""
    return _getattr(cell, "layout", {}) or {}


def _get_text_anchor(layout: Any) -> Any:
    """Restituisce l'ancora di testo di un layout."""
    return _getattr(layout, "text_anchor", None) or _getattr(layout, "textAnchor", {}) or {}


def _get_text_segments(anchor: Any) -> Sequence[Any]:
    """Restituisce i segmenti di testo dell'ancora."""
    return _getattr(anchor, "text_segments", None) or _getattr(anchor, "textSegments", []) or []


def _extract_text_from_segments(segments: Iterable[Any], full_text: str) -> str:
    """Compone il testo concatenando tutti i segmenti indicati."""
    text = ""
    for seg in segments:
        start = _getattr(seg, "start_index", None)
        if start is None:
            start = _getattr(seg, "startIndex", 0)
        end = _getattr(seg, "end_index", None)
        if end is None:
            end = _getattr(seg, "endIndex", 0)
        try:
            start = int(start)
            end = int(end)
        except Exception:
            continue
        text += full_text[start:end]
    return text.strip()


def _cell_text(cell: Any, full_text: str) -> str:
    """Estrae il testo da una cella di tabella."""
    layout = _get_layout(cell)
    anchor = _get_text_anchor(layout)
    segments = _get_text_segments(anchor)
    return _extract_text_from_segments(segments, full_text) if segments else ""


def _parse_number(value_str: Union[str, None]) -> Optional[float]:
    """Converte una stringa in float, gestendo il formato italiano (virgola).

    Se ``value_str`` è ``None`` o non è convertibile in numero, restituisce
    ``None``.
    """
    if not value_str:
        return None
    try:
        cleaned = value_str.replace(".", "").replace(",", ".")
        return float(cleaned)
    except Exception:
        return None