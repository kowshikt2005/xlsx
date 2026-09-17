import io
import streamlit as st
import pandas as pd


def safe_display_df(df):
    display_df = df.copy()
    for col in display_df.columns:
        try:
            if hasattr(display_df[col], "dtype") and display_df[col].dtype == object:
                display_df[col] = display_df[col].apply(
                    lambda x: str(x) if x is not None else ""
                )
            else:
                display_df[col] = display_df[col].astype(str)
        except Exception:
            display_df[col] = display_df[col].astype(str)
    return display_df


@st.dialog("Excel Cleaner", width="large", dismissible=True)
def open_cleaner():
    step = st.session_state["current_step"]
    total_steps = 4

    st.progress(step / total_steps, text=f"Step {step} of {total_steps}")
    st.divider()

    # ── Step 1: Upload ───────────────────────────────────────────────────────

    if step == 1:
        uploaded_file = st.file_uploader(
            "Upload file",
            type=["xlsx", "xls", "csv"],
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            try:
                raw_df = pd.read_excel(uploaded_file, header=None)
                st.session_state["raw_df"] = raw_df
                st.session_state["file_name"] = uploaded_file.name
            except Exception as e:
                st.error(f"Could not read file: {e}")
                return

            st.success(
                f"Loaded: {uploaded_file.name} "
                f"({raw_df.shape[0]:,} rows, {raw_df.shape[1]:,} columns)"
            )

            st.dataframe(
                safe_display_df(raw_df),
                width="stretch",
                height=400,
                hide_index=True,
            )
        else:
            st.info("Upload an Excel or CSV file to get started.")

        st.divider()

        _, col_next = st.columns([1, 1])
        with col_next:
            if st.button(
                "Next",
                type="primary",
                width="stretch",
                disabled=st.session_state.get("raw_df") is None,
            ):
                st.session_state["current_step"] = 2
                st.rerun()

    # ── Step 2: Header Row ───────────────────────────────────────────────────

    elif step == 2:
        raw_df = st.session_state["raw_df"]
        if raw_df is None:
            st.session_state["current_step"] = 1
            st.rerun()
            return

        st.subheader("Select Header Row")

        non_empty_counts = raw_df.notna().sum(axis=1).tolist()
        suggested_row = non_empty_counts.index(max(non_empty_counts))

        header_row = st.number_input(
            "Data starts from row",
            min_value=1,
            max_value=len(raw_df),
            value=suggested_row + 1,
            step=1,
        )

        header_idx = header_row - 1

        new_columns = raw_df.iloc[header_idx].astype(str).tolist()
        seen = {}
        unique_columns = []
        for col in new_columns:
            if col in seen:
                seen[col] += 1
                unique_columns.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_columns.append(col)

        cleaned_df = raw_df.iloc[header_idx + 1:].copy()
        cleaned_df.columns = unique_columns
        cleaned_df.reset_index(drop=True, inplace=True)

        st.success(
            f"Row {header_row} selected. {len(unique_columns)} columns detected."
        )

        st.dataframe(
            safe_display_df(cleaned_df),
            width="stretch",
            height=400,
            hide_index=True,
        )

        st.divider()

        col_back, _, col_next = st.columns([1, 2, 1])
        with col_back:
            if st.button("Back", width="stretch"):
                st.session_state["current_step"] = 1
                st.rerun()
        with col_next:
            if st.button("Next", type="primary", width="stretch"):
                st.session_state["cleaned_df"] = cleaned_df
                st.session_state["unique_columns"] = unique_columns
                st.session_state["current_step"] = 3
                st.rerun()

    # ── Step 3: Edit Columns ─────────────────────────────────────────────────

    elif step == 3:
        cleaned_df = st.session_state["cleaned_df"]
        unique_columns = st.session_state["unique_columns"]
        if cleaned_df is None:
            st.session_state["current_step"] = 2
            st.rerun()
            return

        left, right = st.columns([1, 1])

        with left:
            st.subheader("Edit Columns")

            column_editor_df = pd.DataFrame({
                "Original Name": unique_columns,
                "New Name": unique_columns,
                "Delete?": [False] * len(unique_columns),
            })

            edited_df = st.data_editor(
                column_editor_df,
                column_config={
                    "Original Name": st.column_config.TextColumn(
                        "Original Name",
                        disabled=True,
                    ),
                    "New Name": st.column_config.TextColumn(
                        "New Name",
                        help="Type a new name, or leave as-is to keep the original.",
                    ),
                    "Delete?": st.column_config.CheckboxColumn(
                        "Delete?",
                        help="Tick to remove this column.",
                        default=False,
                    ),
                },
                disabled=["Original Name"],
                hide_index=True,
                width="stretch",
                key="column_editor",
            )

            cols_to_delete = edited_df[edited_df["Delete?"] == True].shape[0]
            cols_to_keep = edited_df[edited_df["Delete?"] != True].shape[0]

            st.caption(f"Keeping: {cols_to_keep}  |  Deleting: {cols_to_delete}")

            if cols_to_keep == 0:
                st.warning("Keep at least one column.")

            keep_mask = edited_df["Delete?"] != True
            keep_rows = edited_df[keep_mask]

            rename_map = {}
            for _, row in keep_rows.iterrows():
                original = row["Original Name"]
                new_name = row["New Name"]
                if pd.notna(new_name) and str(new_name).strip() != "":
                    rename_map[original] = str(new_name).strip()
                else:
                    rename_map[original] = original

            cols_to_keep_list = keep_rows["Original Name"].tolist()
            final_df = cleaned_df[cols_to_keep_list].copy()
            final_df.rename(columns=rename_map, inplace=True)

        with right:
            st.subheader("Preview")
            if cols_to_keep > 0:
                st.dataframe(
                    safe_display_df(final_df),
                    width="stretch",
                    height=400,
                    hide_index=True,
                )
            else:
                st.info("No columns selected.")

        st.divider()

        col_back, _, col_next = st.columns([1, 2, 1])
        with col_back:
            if st.button("Back", width="stretch"):
                st.session_state["current_step"] = 2
                st.rerun()
        with col_next:
            if st.button(
                "Next",
                type="primary",
                width="stretch",
                disabled=cols_to_keep == 0,
            ):
                st.session_state["final_df"] = final_df
                st.session_state["current_step"] = 4
                st.rerun()

    # ── Step 4: Download ─────────────────────────────────────────────────────

    elif step == 4:
        final_df = st.session_state["final_df"]
        if final_df is None:
            st.session_state["current_step"] = 3
            st.rerun()
            return

        left, right = st.columns([1, 1])

        with left:
            st.subheader("Download")

            original_stem = st.session_state.get("file_name", "output")
            if "." in original_stem:
                original_stem = original_stem.rsplit(".", 1)[0]

            filename = st.text_input(
                "Filename",
                value=f"{original_stem}_cleaned.xlsx",
            )

            c1, c2 = st.columns(2)
            c1.metric("Rows", f"{final_df.shape[0]:,}")
            c2.metric("Columns", f"{final_df.shape[1]:,}")

            st.divider()

            buffer = io.BytesIO()
            final_df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            st.download_button(
                label="Download Cleaned Excel",
                data=buffer,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
            )

        with right:
            st.subheader("Final Preview")
            st.dataframe(
                safe_display_df(final_df),
                width="stretch",
                height=400,
                hide_index=True,
            )

        st.divider()

        col_back, _ = st.columns([1, 3])
        with col_back:
            if st.button("Back", width="stretch"):
                st.session_state["current_step"] = 3
                st.rerun()


st.set_page_config(page_title="Excel Cleaner", page_icon=None, layout="wide")

st.markdown(
    """
    <style>
        [data-testid="stDialog"] {
            max-width: 95vw !important;
            width: 95vw !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "current_step" not in st.session_state:
    st.session_state["current_step"] = 1
    st.session_state["raw_df"] = None
    st.session_state["file_name"] = None
    st.session_state["cleaned_df"] = None
    st.session_state["unique_columns"] = None
    st.session_state["final_df"] = None

open_cleaner()
