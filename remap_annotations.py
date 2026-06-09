"""
PDF Annotation Remapper
=======================
Moves annotations from an annotated "source" PDF to a new "target" PDF
by anchoring each annotation to the nearest text snippet it originally
pointed at, then finding that same text in the new PDF and repositioning
the annotation accordingly.

Requirements:
 pip install pymupdf

Usage:
 python remap_annotations.py \
 --source "JEMPERLI DTC Site Update_4_ANNOTATED.pdf" \
 --target "JEMPERLI DTC Site Update_5.pdf" \
 --output "JEMPERLI DTC Site Update_5_ANNOTATED.pdf" \
 --page 1
 --debug
"""

import argparse
import sys
from dataclasses import dataclass, field
from typing import Optional
import fitz # PyMuPDF


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AnnotInfo:
 index: int
 subtype: str
 rect: fitz.Rect
 arrow_tip: Optional[fitz.Point]
 anchor_text: str
 anchor_rect: fitz.Rect
 vertices: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_arrow_tip(annot: fitz.Annot) -> Optional[fitz.Point]:
 subtype = annot.type[1]

 if subtype == "Line":
 verts = annot.vertices
 if verts and len(verts) >= 2:
 return fitz.Point(verts[-1])

 if subtype == "PolyLine":
 verts = annot.vertices
 if verts:
 return fitz.Point(verts[-1])

 if subtype == "FreeText":
 cp = annot.callout_point
 if cp is not None:
 return fitz.Point(cp)
 r = annot.rect
 return fitz.Point(r.x0, r.y1)

 return annot.rect.tl + (annot.rect.br - annot.rect.tl) * 0.5


def _closest_word(page: fitz.Page, point: fitz.Point, radius: float = 80) -> tuple:
 words = page.get_text("words")
 best_text = ""
 best_rect = None
 best_dist = float("inf")

 for w in words:
 wx0, wy0, wx1, wy1, wtext = w[0], w[1], w[2], w[3], w[4]
 cx = (wx0 + wx1) / 2
 cy = (wy0 + wy1) / 2
 dist = ((cx - point.x) ** 2 + (cy - point.y) ** 2) ** 0.5
 if dist < best_dist and dist <= radius:
 best_dist = dist
 best_text = wtext
 best_rect = fitz.Rect(wx0, wy0, wx1, wy1)

 return best_text, best_rect


def _find_text_on_page(page: fitz.Page, text: str) -> Optional[fitz.Rect]:
 hits = page.search_for(text, quads=False)
 if hits:
 return hits[0]
 hits = page.search_for(text.lower(), quads=False)
 if hits:
 return hits[0]
 return None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def extract_annotations(doc: fitz.Document, page_num: int, debug: bool = False) -> list[AnnotInfo]:
 page = doc[page_num]
 results = []

 for idx, annot in enumerate(page.annots()):
 subtype = annot.type[1]
 tip = _get_arrow_tip(annot)
 anchor_text, anchor_rect = ("", fitz.Rect()) if tip is None else _closest_word(page, tip)

 info = AnnotInfo(
 index=idx,
 subtype=subtype,
 rect=fitz.Rect(annot.rect),
 arrow_tip=tip,
 anchor_text=anchor_text,
 anchor_rect=anchor_rect if anchor_rect else fitz.Rect(),
 vertices=list(annot.vertices or []),
 )
 results.append(info)

 if debug:
 print(f" Annot #{idx:02d} [{subtype:12s}] rect={annot.rect} tip={tip} anchor='{anchor_text}' anchor_rect={anchor_rect}")

 return results


def remap_annotations(
 source_path: str,
 target_path: str,
 output_path: str,
 page_num: int = 1,
 debug: bool = False,
) -> None:
 src_doc = fitz.open(source_path)
 tgt_doc = fitz.open(target_path)

 src_page = src_doc[page_num]
 tgt_page = tgt_doc[page_num]

 print(f"\n── Source: {source_path} (page {page_num + 1})")
 print(f"── Target: {target_path} (page {page_num + 1})\n")

 annotations = extract_annotations(src_doc, page_num, debug=debug)

 moved = 0
 skipped = 0

 for info in annotations:
 if not info.anchor_text:
 print(f" ⚠ Annot #{info.index:02d} [{info.subtype}] — no anchor text found, copying as-is.")
 delta = fitz.Point(0, 0)
 else:
 new_rect = _find_text_on_page(tgt_page, info.anchor_text)
 if new_rect is None:
 print(f" ✗ Annot #{info.index:02d} [{info.subtype}] — anchor '{info.anchor_text}' NOT found in target, copying as-is.")
 delta = fitz.Point(0, 0)
 skipped += 1
 else:
 old_tl = info.anchor_rect.tl
 new_tl = new_rect.tl
 delta = new_tl - old_tl
 if debug or abs(delta.x) > 0.5 or abs(delta.y) > 0.5:
 print(f" ✓ Annot #{info.index:02d} [{info.subtype}] anchor='{info.anchor_text}' Δ=({delta.x:+.1f}, {delta.y:+.1f})")
 moved += 1

 src_annots = list(src_page.annots())
 src_annot = src_annots[info.index]
 _copy_annot_with_delta(src_annot, tgt_page, delta)

 tgt_doc.save(output_path, garbage=4, deflate=True)
 print(f"\n── Saved → {output_path}")
 print(f" Moved: {moved} | Unchanged/skipped: {skipped} | Total: {len(annotations)}\n")


def _copy_annot_with_delta(src_annot: fitz.Annot, tgt_page: fitz.Page, delta: fitz.Point) -> None:
 subtype = src_annot.type[1]
 info = src_annot.info
 colors = src_annot.colors
 opacity = src_annot.opacity
 border = src_annot.border

 old_rect = src_annot.rect
 new_rect = old_rect + delta

 def shift_pts(pts):
 return [p + delta for p in pts]

 new_annot = None

 if subtype == "FreeText":
 new_annot = tgt_page.add_freetext_annot(
 new_rect,
 info.get("content", ""),
 fontsize=10,
 )
 verts = src_annot.vertices
 if verts:
 new_annot.set_vertices(shift_pts(verts))

 elif subtype == "Line":
 verts = src_annot.vertices or []
 if len(verts) >= 2:
 p1, p2 = fitz.Point(verts[0]) + delta, fitz.Point(verts[1]) + delta
 else:
 p1 = old_rect.tl + delta
 p2 = old_rect.br + delta
 new_annot = tgt_page.add_line_annot(p1, p2)

 elif subtype == "PolyLine":
 verts = src_annot.vertices or []
 if verts:
 new_annot = tgt_page.add_polyline_annot(shift_pts([fitz.Point(v) for v in verts]))

 elif subtype == "Square":
 new_annot = tgt_page.add_rect_annot(new_rect)

 elif subtype == "Circle":
 new_annot = tgt_page.add_circle_annot(new_rect)

 elif subtype in ("Highlight", "Underline", "StrikeOut", "Squiggly"):
 quads = src_annot.vertices
 if quads:
 shifted_quads = [fitz.Point(p) + delta for p in quads]
 if subtype == "Highlight":
 new_annot = tgt_page.add_highlight_annot(shifted_quads)
 elif subtype == "Underline":
 new_annot = tgt_page.add_underline_annot(shifted_quads)
 elif subtype == "StrikeOut":
 new_annot = tgt_page.add_strikeout_annot(shifted_quads)
 elif subtype == "Squiggly":
 new_annot = tgt_page.add_squiggly_annot(shifted_quads)

 elif subtype == "Ink":
 raw = src_annot.vertices
 if raw:
 strokes = [[fitz.Point(p) + delta for p in raw]]
 new_annot = tgt_page.add_ink_annot(strokes)

 elif subtype == "Stamp":
 new_annot = tgt_page.add_stamp_annot(new_rect, stamp=info.get("name", 0))

 else:
 print(f" ⚠ Unhandled subtype '{subtype}' — skipping.")
 return

 if new_annot is None:
 return

 try:
 new_annot.set_colors(stroke=colors.get("stroke"), fill=colors.get("fill"))
 except Exception:
 pass
 try:
 new_annot.set_opacity(opacity)
 except Exception:
 pass
 try:
 if border.get("width"):
 new_annot.set_border(border)
 except Exception:
 pass
 try:
 new_annot.set_info(info)
 except Exception:
 pass

 new_annot.update()


# ---------------------------------------------------------------------------
# In-memory entry point (used by Streamlit app)
# ---------------------------------------------------------------------------

def remap_annotations_in_memory(
 source_bytes: bytes,
 target_bytes: bytes,
 page_num: int = 1,
 debug: bool = False,
) -> tuple[bytes, list[str]]:
 log_lines: list[str] = []

 def log(msg: str):
 log_lines.append(msg)
 print(msg)

 src_doc = fitz.open(stream=source_bytes, filetype="pdf")
 tgt_doc = fitz.open(stream=target_bytes, filetype="pdf")

 src_page = src_doc[page_num]
 tgt_page = tgt_doc[page_num]

 log(f"── Source page {page_num + 1} ({src_page.rect.width:.0f}×{src_page.rect.height:.0f} pt)")
 log(f"── Target page {page_num + 1} ({tgt_page.rect.width:.0f}×{tgt_page.rect.height:.0f} pt)")
 log("")

 annotations = extract_annotations(src_doc, page_num, debug=debug)

 if not annotations:
 log("⚠ No annotations found on the specified page.")

 moved = 0
 skipped = 0
 src_annots_list = list(src_page.annots())

 for info in annotations:
 if not info.anchor_text:
 log(f" ⚠ Annot #{info.index:02d} [{info.subtype}] — no anchor text found, copying as-is.")
 delta = fitz.Point(0, 0)
 else:
 new_rect = _find_text_on_page(tgt_page, info.anchor_text)
 if new_rect is None:
 log(f" ✗ Annot #{info.index:02d} [{info.subtype}] — anchor '{info.anchor_text}' NOT found in target, copying as-is.")
 delta = fitz.Point(0, 0)
 skipped += 1
 else:
 old_tl = info.anchor_rect.tl
 new_tl = new_rect.tl
 delta = new_tl - old_tl
 if debug or abs(delta.x) > 0.5 or abs(delta.y) > 0.5:
 log(f" ✓ Annot #{info.index:02d} [{info.subtype}] anchor='{info.anchor_text}' Δ=({delta.x:+.1f}, {delta.y:+.1f})")
 moved += 1

 _copy_annot_with_delta(src_annots_list[info.index], tgt_page, delta)

 log("")
 log(f"── Remapped: {moved} | Unchanged/skipped: {skipped} | Total: {len(annotations)}")

 output_bytes = tgt_doc.tobytes(garbage=4, deflate=True)
 return output_bytes, log_lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
 parser = argparse.ArgumentParser(
 description="Remap PDF annotations from an annotated source to a new target PDF.",
 )
 parser.add_argument("--source", required=True)
 parser.add_argument("--target", required=True)
 parser.add_argument("--output", required=True)
 parser.add_argument("--page", type=int, default=1)
 parser.add_argument("--debug", action="store_true")
 args = parser.parse_args()

 try:
 import fitz
 except ImportError:
 print("ERROR: PyMuPDF is not installed. Run: pip install pymupdf")
 sys.exit(1)

 remap_annotations(
 source_path=args.source,
 target_path=args.target,
 output_path=args.output,
 page_num=args.page,
 debug=args.debug,
 )


if __name__ == "__main__":
 main()