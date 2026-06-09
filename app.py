"""
PDF Annotation Remapper - Streamlit App
"""

import streamlit as st
import fitz # PyMuPDF
from remap_annotations import extract_annotations, remap_annotations_in_memory

# Page config
st.set_page_config(
 page_title="PDF Annotation Remapper",
 page_icon="📌",
 layout="centered",
)

# Header
st.title("PDF Annotation Remapper")
st.markdown(
 "Upload an **annotated PDF** and a **new version** of the same document. "
 "The app will move all annotations to match where the content has shifted."
)
st.divider()

# File uploaders
col1, col2 = st.columns(2)

with col1:
 st.subheader("1. Annotated PDF")
 source_file = st.file_uploader(
 "The current PDF that already has annotations",
 type=["pdf"],
 key="source",
 label_visibility="collapsed",
 )
 if source_file:
 st.success("Uploaded: " + source_file.name)

with col2:
 st.subheader("2. New PDF (no annotations)")
 target_file = st.file_uploader(
 "The new version of the document without annotations",
 type=["pdf"],
 key="target",
 label_visibility="collapsed",
 )
 if target_file:
 st.success("Uploaded: " + target_file.name)

st.divider()

# Options
st.subheader("3. Options")

col3, col4 = st.columns([1, 2])

with col3:
 page_num = st.number_input(
 "Page with annotations (1 = first page)",
 min_value=1,
 max_value=200,
 value=2,
 step=1,
 help="Which page contains the annotations?",
 )

with col4:
 show_debug = st.checkbox(
 "Show detailed remapping log",
 value=False,
 help="Displays each annotation's anchor word and how far it moved.",
 )

st.divider()

# Run
st.subheader("4. Remap")

run_disabled = not (source_file and target_file)

if run_disabled:
 st.info("Upload both PDFs above to enable remapping.")

if st.button("Remap Annotations", disabled=run_disabled, use_container_width=True, type="primary"):
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

 moved_count = sum(1 for l in log_lines if l.strip().startswith("✓"))
 skipped_count = sum(1 for l in log_lines if l.strip().startswith(("✗", "⚠")))
 total_count = moved_count + skipped_count

 st.success(
 "Done! "
 + str(moved_count) + " annotation(s) remapped, "
 + str(skipped_count) + " copied as-is, "
 + str(total_count) + " total."
 )

 base_name = target_file.name.replace(".pdf", "")
 output_name = base_name + "_ANNOTATED.pdf"

 st.download_button(
 label="Download Annotated PDF",
 data=output_bytes,
 file_name=output_name,
 mime="application/pdf",
 use_container_width=True,
 )

 if show_debug and log_lines:
 with st.expander("Remapping log", expanded=True):
 st.code("\n".join(log_lines), language=None)

 except IndexError:
 st.error(
 "Page " + str(page_num) + " does not exist in one of the uploaded PDFs. "
 "Check the page number and try again."
 )
 except Exception as e:
 st.error("Something went wrong: " + str(e))
 if show_debug:
 import traceback
 st.code(traceback.format_exc())

# Footer
st.divider()
st.caption("Powered by PyMuPDF | Built for Omnicom Production")
