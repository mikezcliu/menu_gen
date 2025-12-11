import os
import json
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

from dotenv import load_dotenv  # <--- THIS WAS MISSING

# ==========================================
# 👇 PASTE YOUR KEY INSIDE THE QUOTES BELOW
# ==========================================
API_KEY = "AIzaSyDR5owm-muQAnrPkeGMBCsXGGYCeA2_mWs"
# ==========================================


# ==========================================
# text models defined here
# ==========================================
TEXT_MODEL_ID = "gemini-2.0-flash"
IMAGE_MODEL_ID = "imagen-4.0-generate-001"
# ==========================================



def main():
    st.set_page_config(page_title="Nano Menu", layout="wide")
    st.title("🍌 Nano Banana Menu Visualizer")

    # Simple key guard
    if API_KEY == "PASTE_YOUR_KEY_HERE" or not API_KEY:
        st.error("🛑 Missing API Key. Please set API_KEY or GEMINI_API_KEY.")
        st.stop()

    client = genai.Client(api_key=API_KEY)

    uploaded_file = st.file_uploader(
        "Upload Menu Image", type=["jpg", "jpeg", "png"]
    )

    if uploaded_file:
        # Read bytes once so we can reuse them
        image_bytes = uploaded_file.getvalue()
        image_mime = uploaded_file.type or "image/jpeg"

        col1, col2 = st.columns([1, 2])

        # ==============
        # LEFT COLUMN: show original menu
        # ==============
        with col1:
            # Use raw bytes (Streamlit handles them with PIL internally)
            st.image(
                image_bytes,
                caption="Original Menu",
                use_container_width=True,
            )
            process_btn = st.button("Generate Dish Photos", type="primary")

        # ==============
        # RIGHT COLUMN: process & generate
        # ==============
        if process_btn:
            with col2:
                # --- STEP 1: READ MENU (TEXT MODEL) ---
                with st.status("Reading menu text...", expanded=True) as status:
                    extract_prompt = (
                        "You are reading a restaurant menu image.\n\n"
                        "Task: Identify the 10 most distinct main dish names from this menu.\n"
                        "Return ONLY a JSON array of strings, where each string is a dish name.\n\n"
                        "Example output:\n"
                        "[\"Truffle Burger\", \"Caesar Salad\", \"Margherita Pizza\", \"Lobster Bisque\"]"
                    )

                    # Strict JSON schema: array of strings
                    schema = {
                        "type": "array",
                        "items": {"type": "string"},
                    }

                    dish_list = []

                    try:
                        response = client.models.generate_content(
                            model=TEXT_MODEL_ID,
                            contents=[
                                extract_prompt,
                                types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type=image_mime,
                                ),
                            ],
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=schema,
                            ),
                        )

                        # Thanks to schema + JSON mode, this should already be a list[str]
                        data = response.parsed

                        if not isinstance(data, list):
                            raise ValueError(
                                f"Expected a list of dish names, got: {type(data)}"
                            )

                        # Normalize to strings and filter empties
                        dish_list = [
                            str(d).strip()
                            for d in data
                            if str(d).strip()
                        ]

                        if not dish_list:
                            raise ValueError(
                                "Model returned an empty list of dishes."
                            )

                        status.write(f"Found dishes: {dish_list}")
                        status.update(
                            label="Menu read successfully ✅",
                            state="complete",
                            expanded=False,
                        )

                    except Exception as e:
                        # Helpful debug: show parsed + raw text if we have them
                        st.caption("Debug: parsed response from model:")
                        try:
                            st.json(data)
                        except Exception:
                            st.write("No parsed data available.")
                        st.caption("Debug: raw text response (if any):")
                        try:
                            st.code(getattr(response, "text", ""), language="json")
                        except Exception:
                            st.write("No raw text available.")
                        st.error(f"Error reading menu: {e}")
                        st.stop()

                # --- STEP 2: GENERATE IMAGES (IMAGE MODEL) ---
                st.subheader("AI Generated Dish Photos")
                grid_cols = st.columns(2)

                for i, dish in enumerate(dish_list):
                    col = grid_cols[i % 2]
                    with col:
                        with st.spinner(f"Plating {dish}..."):
                            try:
                                img_prompt = (
                                    f"Professional food photograph of {dish}, "
                                    "Michelin-star restaurant style plating, "
                                    "soft studio lighting, 4k resolution."
                                )

                                result = client.models.generate_images(
                                    model=IMAGE_MODEL_ID,
                                    prompt=img_prompt,
                                    config=types.GenerateImagesConfig(
                                        number_of_images=1,
                                        aspect_ratio="1:1",
                                    ),
                                )

                                # Convert Google image object → raw bytes → Streamlit
                                generated = result.generated_images[0]
                                image_bytes_out = generated.image.image_bytes

                                # Streamlit can take raw bytes directly
                                st.image(
                                    image_bytes_out,
                                    caption=dish,
                                    use_container_width=True,
                                )

                            except Exception as e:
                                st.warning(f"Could not generate {dish}")
                                st.caption(f"Error: {e}")


if __name__ == "__main__":
    main()