"""
PDF Annotation Remapper - Streamlit App
"""

import streamlit as st
from remap_annotations import extract_annotations, remap_annotations_in_memory

st.set_page_config(page_title="PDF Annotation Remapper", page_icon="📌", layout="centered")

st.title("PDF Annotation Remapper")
st.markdown("Upload an **annotated PDF** and a **new version** of the same document. The app will move all annotations to match where the content has shifted.")
st.divider()

col1, col2 = st.columns(2)
source_file = col1.file_uploader("1. Annotated PDF (has annotations)", type=["pdf"], key="source")
target_file = col2.file_uploader("2. New PDF (no annotations yet)", type=["pdf"], key="target")

st.divider()

col3, col4 = st.columns([1, 2])
page_num = col3.number_input("Page number with annotations", min_value=1, max_value=200, value=2, step=1)
show_debug = col4.checkbox("Show detailed remapping log", value=False)

st.divider()

if not source_file or not target_file:
 st.info("Upload both PDFs above to enable remapping.")

run = st.button("Remap Annotations", disabled=not (source_file and target_file), use_container_width=True, type="primary")

if run:
 with st.spinner("Remapping annotations..."):
 try:
 source_bytes = source_file.read()
 target_bytes = target_file.read()

 output_bytes, log_lines = remap_annotations_in_memory(
 source_bytes=source_bytes,
 target_bytes=target_bytes,
 page_num=page_num - 1,
 debug=show_debug,
 )

 moved_count = sum(1 for line in log_lines if line.strip().startswith("✓"))
 skipped_count = sum(1 for line in log_lines if line.strip().startswith(("✗", "⚠")))
 total_count = moved_count + skipped_count

 st.success("Done! " + str(moved_count) + " remapped, " + str(skipped_count) + " unchanged, " + str(total_count) + " total.")

 output_name = target_file.name.replace(".pdf", "") + "_ANNOTATED.pdf"

 st.download_button(label="Download Annotated PDF", data=output_bytes, file_name=output_name, mime="application/pdf", use_container_width=True)

 if show_debug and log_lines:
 with st.expander("Remapping log", expanded=True):
 st.code("\n".join(log_lines), language=None)

 except IndexError:
 st.error("Page " + str(page_num) + " does not exist in one of the PDFs. Check the page number and try again.")
 except Exception as e:
 st.error("Something went wrong: " + str(e))
 if show_debug:
 import traceback
 st.code(traceback.format_exc())

st.divider()
st.caption("Powered by PyMuPDF | Built for Omnicom Production")
