"""
Phase 40: PDF Visual Extractor.

Uses the existing pypdf library (already a project dependency) and Pillow
to extract embedded images, detect figure/table captions, and classify
visual types from PDF pages.

Design principles:
- Reuses pypdf.PdfReader which the existing loader already uses.
- Does NOT replace the text extraction pipeline.
- Visual extraction failure is non-fatal: the document upload still succeeds.
- No new heavyweight dependencies (no fitz/PyMuPDF, no tabula, no OCR).
- Table detection uses regex on per-page extracted text (safe, zero-dependency).
- Caption detection uses regex (Figure N / Table N patterns).

Supported visual types (controlled vocabulary):
    image       — raw embedded raster image with no figure caption
    figure      — embedded image associated with a figure caption
    diagram     — embedded image associated with a diagram/illustration caption
    chart       — embedded image associated with a chart/graph caption
    table       — table detected from text layout (no image asset)
    page_region — fallback for vector/drawing-only regions (not yet implemented)
    unknown     — classified when confidence is insufficient
"""

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("eduva.visual_extractor")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExtractedVisual:
    """
    Represents a single detected visual element from a PDF page.
    All fields are safe to store in DocumentVisual without modification.
    """
    page_number: int           # 1-based page number
    visual_type: str           # controlled vocabulary (see module docstring)
    asset_path: Optional[str]  # absolute filesystem path to saved image, or None
    asset_url: Optional[str]   # public URL path e.g. /static/documents/3/img.jpg
    caption: Optional[str]     # detected caption text, or None
    width: Optional[int]       # pixel width (images only)
    height: Optional[int]      # pixel height (images only)
    image_format: Optional[str]  # 'JPEG', 'PNG', 'JPEG2000', etc.
    image_index: int           # index within page images; -1 for text-detected visuals
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Caption patterns
# ---------------------------------------------------------------------------

# Matches figure/diagram/illustration captions:
#   "Figure 3.", "Fig. 2a:", "Figure: Neural network", "Illustration 1"
_FIGURE_PATTERN = re.compile(
    r"(?:^|\n)\s*"
    r"(?P<label>(?:Fig(?:ure)?|Diagram|Illustration|Exhibit|Image)\s*[0-9]*\.?\s*[\.:–\-]?)"
    r"\s*(?P<text>[^\n]{0,200})",
    re.IGNORECASE | re.MULTILINE,
)

# Matches chart/graph captions:
#   "Chart 1:", "Graph 2.", "Plot 1 —"
_CHART_PATTERN = re.compile(
    r"(?:^|\n)\s*"
    r"(?P<label>(?:Chart|Graph|Plot)\s*[0-9]*\.?\s*[\.:–\-]?)"
    r"\s*(?P<text>[^\n]{0,200})",
    re.IGNORECASE | re.MULTILINE,
)

# Matches table captions:
#   "Table 1.", "Table 2: Comparison of…", "TABLE I."
_TABLE_PATTERN = re.compile(
    r"(?:^|\n)\s*"
    r"(?P<label>Table\s*[0-9IVXivx]*\.?\s*[\.:–\-]?)"
    r"\s*(?P<text>[^\n]{0,200})",
    re.IGNORECASE | re.MULTILINE,
)

# Detect table-like structure in text (rows of pipe-separated or space-aligned data)
_TABLE_ROW_PATTERN = re.compile(
    r"^(?:\S+\s{2,}){2,}\S+$",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str) -> str:
    """Remove path traversal characters from an image filename."""
    # Normalize Unicode, remove non-ASCII that could confuse filesystems
    name = unicodedata.normalize("NFKD", name)
    # Keep only safe characters
    name = re.sub(r"[^\w\-.]", "_", name)
    # Prevent traversal
    name = name.lstrip("./\\")
    return name or "image"


def _clean_caption(text: str) -> Optional[str]:
    """Normalize caption text, return None if it's effectively empty."""
    cleaned = text.strip()
    # Strip trailing punctuation artifacts
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if len(cleaned) >= 3 else None


def _detect_captions_on_page(page_text: str) -> dict:
    """
    Scan a page's text for caption-like patterns.

    Returns:
        dict with keys 'figure', 'chart', 'table' each holding a list of
        (label, caption_text) tuples found on this page.
    """
    result = {"figure": [], "chart": [], "table": []}

    for m in _FIGURE_PATTERN.finditer(page_text):
        cap = _clean_caption(m.group("label") + " " + m.group("text"))
        if cap:
            result["figure"].append(cap)

    for m in _CHART_PATTERN.finditer(page_text):
        cap = _clean_caption(m.group("label") + " " + m.group("text"))
        if cap:
            result["chart"].append(cap)

    for m in _TABLE_PATTERN.finditer(page_text):
        cap = _clean_caption(m.group("label") + " " + m.group("text"))
        if cap:
            result["table"].append(cap)

    return result


def _detect_table_regions(page_text: str) -> int:
    """
    Detect table-like regions from whitespace-aligned text layout.
    Returns count of suspected table rows (>= 3 consecutive rows = 1 table region).
    """
    consecutive = 0
    tables_found = 0
    for line in page_text.split("\n"):
        if _TABLE_ROW_PATTERN.match(line.strip()):
            consecutive += 1
        else:
            if consecutive >= 3:
                tables_found += 1
            consecutive = 0
    if consecutive >= 3:
        tables_found += 1
    return tables_found


def _classify_image_type(caption: Optional[str]) -> str:
    """
    Classify a visual type based on its associated caption text.
    Falls back to 'image' if no caption or no keyword match.
    """
    if not caption:
        return "image"

    lower = caption.lower()
    if any(kw in lower for kw in ["chart", "graph", "plot", "histogram", "bar chart", "pie chart"]):
        return "chart"
    if any(kw in lower for kw in ["diagram", "architecture", "flow", "flowchart", "circuit", "schematic"]):
        return "diagram"
    if any(kw in lower for kw in ["fig", "figure", "illustration", "exhibit", "image"]):
        return "figure"
    return "image"


# ---------------------------------------------------------------------------
# Main extractor
# ---------------------------------------------------------------------------

class PDFVisualExtractor:
    """
    Extracts visual elements from a PDF using pypdf.

    Workflow per page:
    1. Extract text → detect captions and table regions.
    2. Iterate page.images → save each image to the document static dir.
    3. Associate images with captions heuristically (same page, sequential).
    4. Emit ExtractedVisual for each image and each detected table.
    """

    STATIC_DOCUMENTS_DIR = Path("static/documents")
    MAX_IMAGE_DIMENSION = 4096  # Skip pathologically large images

    def extract_visuals(
        self,
        file_path: str,
        document_id: int,
        existing_image_names: Optional[set] = None,
    ) -> list[ExtractedVisual]:
        """
        Main entry point. Returns a list of ExtractedVisual objects.
        Never raises — logs errors and returns partial results.

        Args:
            file_path: Absolute or CWD-relative path to the PDF file.
            document_id: Database document ID (used for asset directory).
            existing_image_names: Set of filenames already on disk to avoid duplicates.
        """
        from pypdf import PdfReader  # local import: pypdf is a project dep

        visuals: list[ExtractedVisual] = []
        seen_names: set[str] = existing_image_names or set()

        # Prepare asset directory
        asset_dir = self.STATIC_DOCUMENTS_DIR / str(document_id)
        asset_dir.mkdir(parents=True, exist_ok=True)

        try:
            reader = PdfReader(file_path, strict=False)
        except Exception as exc:
            logger.error(f"[Phase40] Failed to open PDF {file_path}: {exc}")
            return visuals

        logger.info(f"[Phase40] Extracting visuals from document {document_id} ({len(reader.pages)} pages)")

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1  # 1-based

            # Step 1: Extract text and detect captions / tables
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                logger.warning(f"[Phase40] Text extraction failed on page {page_num}: {exc}")
                page_text = ""

            captions_on_page = _detect_captions_on_page(page_text)
            table_count = _detect_table_regions(page_text)

            # Step 2: Process embedded images
            image_visuals = self._extract_page_images(
                page=page,
                page_num=page_num,
                document_id=document_id,
                asset_dir=asset_dir,
                captions=captions_on_page,
                seen_names=seen_names,
            )
            visuals.extend(image_visuals)

            # Step 3: Register detected table regions (text-only, no image asset)
            for table_idx in range(table_count):
                table_caption_list = captions_on_page.get("table", [])
                table_caption = table_caption_list[table_idx] if table_idx < len(table_caption_list) else None
                visuals.append(ExtractedVisual(
                    page_number=page_num,
                    visual_type="table",
                    asset_path=None,
                    asset_url=None,
                    caption=table_caption,
                    width=None,
                    height=None,
                    image_format=None,
                    image_index=-1,
                    metadata={"source": "text_layout_detection"},
                ))

            # Step 4: If captions reference figures but no image was found on this page,
            # record a page_region visual (preserves provenance for Phase 41).
            # Only emit if we have a figure/diagram caption but zero images on the page.
            if (captions_on_page["figure"] or captions_on_page["chart"]) and not image_visuals:
                for fig_cap in captions_on_page["figure"] + captions_on_page["chart"]:
                    visuals.append(ExtractedVisual(
                        page_number=page_num,
                        visual_type="page_region",
                        asset_path=None,
                        asset_url=None,
                        caption=fig_cap,
                        width=None,
                        height=None,
                        image_format=None,
                        image_index=-1,
                        metadata={"source": "caption_without_embedded_image"},
                    ))

        logger.info(f"[Phase40] Extracted {len(visuals)} visuals from document {document_id}")
        return visuals

    def _extract_page_images(
        self,
        page,
        page_num: int,
        document_id: int,
        asset_dir: Path,
        captions: dict,
        seen_names: set,
    ) -> list[ExtractedVisual]:
        """Extract and save all embedded images from a single page."""
        from PIL import Image as PILImage  # Pillow is a project dep

        visuals = []
        # Merge all available captions on this page for assignment
        all_captions = captions.get("figure", []) + captions.get("chart", [])

        try:
            page_images = list(page.images)
        except Exception as exc:
            logger.warning(f"[Phase40] page.images failed on page {page_num}: {exc}")
            return visuals

        for img_idx, img_file in enumerate(page_images):
            try:
                raw_name = _sanitize_filename(img_file.name or f"image_p{page_num}_{img_idx}")

                # We must still process and return the visual even if the file exists on disk
                if raw_name in seen_names:
                    logger.debug(f"[Phase40] Image '{raw_name}' on page {page_num} already processed, but emitting visual record anyway")
                else:
                    seen_names.add(raw_name)

                # Determine output path
                save_path = asset_dir / raw_name

                # Get width/height/format via PIL if available
                width = height = None
                image_format = None
                pil_img = img_file.image  # PIL.Image or None (pypdf provides this)

                if pil_img is not None:
                    width, height = pil_img.size
                    image_format = pil_img.format or _infer_format_from_name(raw_name)

                    # Skip pathologically large images
                    if width and height and (width > self.MAX_IMAGE_DIMENSION or height > self.MAX_IMAGE_DIMENSION):
                        logger.warning(
                            f"[Phase40] Image '{raw_name}' on page {page_num} "
                            f"is very large ({width}x{height}), saving anyway"
                        )

                # Write raw bytes if not already saved (file may exist from prior run)
                if not save_path.exists():
                    with open(save_path, "wb") as fp:
                        fp.write(img_file.data)

                # If PIL gave us None format, try to infer from extension
                if not image_format:
                    image_format = _infer_format_from_name(raw_name)

                # Assign caption: use page captions in order (best effort)
                caption = all_captions[img_idx] if img_idx < len(all_captions) else None

                # Classify type
                visual_type = _classify_image_type(caption)

                asset_url = f"/static/documents/{document_id}/{raw_name}"

                visuals.append(ExtractedVisual(
                    page_number=page_num,
                    visual_type=visual_type,
                    asset_path=str(save_path),
                    asset_url=asset_url,
                    caption=caption,
                    width=width,
                    height=height,
                    image_format=image_format,
                    image_index=img_idx,
                    metadata={"original_name": img_file.name or ""},
                ))

            except Exception as exc:
                logger.warning(
                    f"[Phase40] Failed to process image {img_idx} on page {page_num}: {exc}"
                )
                continue

        return visuals


def _infer_format_from_name(name: str) -> Optional[str]:
    """Guess image format from file extension."""
    ext = Path(name).suffix.lower().lstrip(".")
    _EXT_MAP = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "jp2": "JPEG2000",
        "jb2": "JBIG2",
        "gif": "GIF",
        "bmp": "BMP",
        "tiff": "TIFF",
        "tif": "TIFF",
        "webp": "WEBP",
    }
    return _EXT_MAP.get(ext)
