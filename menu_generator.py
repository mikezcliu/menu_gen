import os
import json
from io import BytesIO

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

from dotenv import load_dotenv


# ==========================================
# text models defined here
# ==========================================
TEXT_MODEL_ID = "gemini-2.0-flash"
IMAGE_MODEL_ID = "imagen-4.0-generate-001"
# ==========================================



def main():
    st.set_page_config(page_title="Nano Menu", layout="wide")

    # --- CHANGED: Sidebar Input for Security ---
    with st.sidebar:
        st.header("Settings")
        api_key_input = st.text_input("Enter Google Gemini API Key", type="password")
        st.caption("Get a free key at [aistudio.google.com](https://aistudio.google.com)")

    st.title("👨‍🍳 Menu Visualizer")
    st.caption("Created by Mike Liu")

    if not api_key_input:
        st.warning("⬅️ Please enter your Google API Key in the sidebar to continue. If you don't have one, ping Mike :)")
        st.stop()

    # Initialize client with the user's input key
    client = genai.Client(api_key=api_key_input)

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
                style_choice = st.session_state["current_style"]
                st.session_state["dish_style"] = style_choice
                st.session_state["dish_items"] = []

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

                st.subheader("AI Generated Dish Photos")
                st.caption(f"Style: **{style_choice}**")

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

                                st.session_state["dish_items"].append({
                                    "name": name,
                                    "description": desc,
                                    "image": image_bytes_out,
                                    "count": 1,
                                    "stock": 100,
                                })
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

            elif st.session_state.get("dish_items"):
                style_label = st.session_state.get("dish_style", "")
                st.subheader("AI Generated Dish Photos")
                if style_label:
                    st.caption(f"Style: **{style_label}**")

                items = st.session_state["dish_items"]
                grid_cols = st.columns(2)
                for i, item in enumerate(items):
                    col = grid_cols[i % 2]
                    with col:
                        btn_row = st.columns([1, 1, 1, 4, 1])
                        with btn_row[0]:
                            if st.button("−", key=f"dec_{i}", help="Decrease count"):
                                if item["count"] > 0:
                                    st.session_state["dish_items"][i]["count"] -= 1
                                    st.rerun()
                        with btn_row[1]:
                            st.markdown(f"**{item['count']}**")
                        with btn_row[2]:
                            if st.button("+", key=f"inc_{i}", help="Increase count"):
                                st.session_state["dish_items"][i]["count"] += 1
                                st.rerun()
                        with btn_row[4]:
                            if st.button("✕", key=f"del_{i}", help=f"Remove {item['name']}"):
                                st.session_state["dish_items"].pop(i)
                                st.rerun()
                        st.image(item["image"], caption=item["name"], use_container_width=True)
                        if item["description"]:
                            st.caption(item["description"])
                        with st.expander("📊 Stock level"):
                            new_stock = st.slider(
                                "Remaining",
                                0, 100,
                                value=item.get("stock", 100),
                                format="%d%%",
                                key=f"stock_{item['name']}",
                            )
                            st.session_state["dish_items"][i]["stock"] = new_stock


if __name__ == "__main__":
    main()
