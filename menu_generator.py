import os
import json
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

from dotenv import load_dotenv

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

    if API_KEY == "PASTE_YOUR_KEY_HERE" or not API_KEY:
        st.error("🛑 Missing API Key. Please set API_KEY or GEMINI_API_KEY.")
        st.stop()

    client = genai.Client(api_key=API_KEY)

    # Remember chosen style across reruns
    if "current_style" not in st.session_state:
        st.session_state["current_style"] = "Michelin fine dining"

    uploaded_file = st.file_uploader(
        "Upload Menu Image", type=["jpg", "jpeg", "png"]
    )

    if uploaded_file:
        image_bytes = uploaded_file.getvalue()
        image_mime = uploaded_file.type or "image/jpeg"

        col1, col2 = st.columns([1, 2])

        # LEFT: original image + style selector + button
        with col1:
            st.image(image_bytes, caption="Original Menu", use_container_width=True)

            # --- STYLE PICKER (user picks FIRST) ---
            current_style = st.session_state["current_style"]
            selected_style = st.radio(
                "Choose photo style (applies to all generated photos)",
                ["Michelin fine dining", "Street food"],
                horizontal=True,
                index=0 if current_style == "Michelin fine dining" else 1,
                key="style_radio",
            )
            st.session_state["current_style"] = selected_style

            generate_btn = st.button("Read Menu & Generate Photos", type="primary")

        # RIGHT: extract menu and generate images
        with col2:
            if generate_btn:
                # --- STEP 1: READ MENU (extract all dishes) ---
                with st.status("Reading menu text...", expanded=True) as status:
                    extract_prompt = (
                        "You are reading a restaurant menu image.\n"
                        "Extract ALL distinct food and drink items.\n"
                        "For each item include:\n"
                        "- name\n"
                        "- description (if available or inferred)\n\n"
                        "Return ONLY JSON matching this schema:\n"
                        "{\n"
                        "  \"items\": [\n"
                        "     {\"name\": \"...\", \"description\": \"...\"},\n"
                        "     ...\n"
                        "  ]\n"
                        "}"
                    )

                    schema = {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
                            }
                        },
                        "required": ["items"],
                    }

                    dish_items = []

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

                        data = response.parsed
                        items = data.get("items", [])

                        for it in items:
                            name = str(it.get("name", "")).strip()
                            desc = str(it.get("description", "")).strip()
                            if name:
                                dish_items.append({"name": name, "description": desc})

                        if not dish_items:
                            raise ValueError("Model returned no dishes.")

                        # Take only the FIRST 10 for generation
                        dish_items = dish_items[:10]

                        status.write(f"Found {len(dish_items)} dishes. Generating photos...")
                        status.update(
                            label="Menu read successfully ✅",
                            state="complete",
                            expanded=False,
                        )

                    except Exception as e:
                        st.caption("Debug: parsed model response:")
                        try:
                            st.json(data)
                        except Exception:
                            st.write("No parsed data.")
                        st.error(f"Error reading menu: {e}")
                        st.stop()

                # --- STEP 2: GENERATE FIRST 10 DISH IMAGES based on chosen style ---
                st.subheader("AI Generated Dish Photos")

                style_choice = st.session_state["current_style"]
                st.caption(f"Style: **{style_choice}**")

                if style_choice == "Michelin fine dining":
                    style_suffix = (
                        "Michelin-star fine dining presentation on elegant plates, "
                        "white tablecloth, soft studio lighting, 4k resolution."
                    )
                else:
                    style_suffix = (
                        "authentic street food style, casual serving containers, "
                        "vibrant colors, handheld or paper serving, 4k resolution."
                    )

                grid_cols = st.columns(2)
                for i, item in enumerate(dish_items):
                    name = item["name"]
                    desc = item.get("description", "")

                    col = grid_cols[i % 2]
                    with col:
                        with st.spinner(f"Plating {name}..."):
                            try:
                                img_prompt = (
                                    f"High-quality food photograph of {name}. "
                                    f"{desc} "
                                    f"{style_suffix}"
                                )

                                result = client.models.generate_images(
                                    model=IMAGE_MODEL_ID,
                                    prompt=img_prompt,
                                    config=types.GenerateImagesConfig(
                                        number_of_images=1,
                                        aspect_ratio="1:1",
                                    ),
                                )

                                generated = result.generated_images[0]
                                image_bytes_out = generated.image.image_bytes

                                st.image(
                                    image_bytes_out,
                                    caption=name,
                                    use_container_width=True,
                                )
                                if desc:
                                    st.caption(desc)

                            except Exception as e:
                                st.warning(f"Could not generate {name}")
                                st.caption(f"Error: {e}")


if __name__ == "__main__":
    main()
