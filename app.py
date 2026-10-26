import io
import os
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# --- CONFIGURATION DATABASE ---
PLACEMENT_SPECS = {
    "RewardsATF": {
        "type": "mockup",
        "mockup_file": "RewardsATF.jpg",
        "mockup_coords": [23, 272, 1055, 594],
        "radius": 40,
        "tag_artboard_size": "1440x450"
    },
    "PT": {
        "type": "multi-template-mockup",
        "radius": 12,
        "tag_artboard_size": "1440x1200",
        "templates": {
            "Parking (Light)": {
                "mockup_file": "Parking_Light.png",
                "mockup_coords": [13, 428, 500, 812],
                "theme": "light"
            },
            "Parking (Dark)": {
                "mockup_file": "Parking_Dark.png",
                "mockup_coords": [13, 428, 500, 812],
                "theme": "dark"
            },
            "Swiggy (Light)": {
                "mockup_file": "Swiggy_Light.png",
                "mockup_coords": [13, 428, 500, 812],
                "theme": "light"
            },
            "Swiggy (Dark)": {
                "mockup_file": "Swiggy_Dark.png",
                "mockup_coords": [13, 428, 500, 812],
                "theme": "dark"
            },
        },
    },
    "CBB": {
        "type": "mockup",
        "mockup_file": "CBB.jpg",
        "mockup_coords": [35, 1108, 1043, 1946],
        "radius": 30,
        "tag_artboard_size": "1440x1200"
    },
    "CBC": {
        "type": "mockup",
        "mockup_file": "CBC2.jpg",
        "mockup_coords": [12, 670, 578, 1142],
        "radius": 18,
        "tag_artboard_size": "1440x1200"
    },
    "Coupon": {
        "type": "overlay",
        "creative_size": [1440, 1080],
        "overlay_file": "ui_overlay.png"
    }
}

# --- HELPER FUNCTIONS ---

def add_rounded_corners(im: Image.Image, rad: int) -> Image.Image:
    """Creates a circular mask to apply rounded corners to an image."""
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)
    
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

def image_to_bytes(image: Image.Image) -> bytes:
    """Saves a PIL image to an in-memory bytes buffer as a JPEG."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def create_zip_archive(files_to_zip: dict) -> bytes:
    """Creates a zip archive from a dictionary of filenames and their byte content."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as zipf:
        for filename, data in files_to_zip.items():
            zipf.writestr(filename, data)
    return zip_buf.getvalue()

def render_pt_text(template: Image.Image, dt_obj: datetime, user_name: str, upi_id: str, theme: str = "light") -> Image.Image:
    """Renders user metadata and formatted timestamp directly onto PT templates."""
    draw = ImageDraw.Draw(template)

    scale_x = template.width / 512.0
    scale_y = template.height / 1024.0

    if theme == "dark":
        name_color = (255, 255, 255)
        upi_color = (154, 160, 166)
    else:
        name_color = (32, 33, 36)
        upi_color = (95, 99, 104)
        
    ts_color = (213, 227, 200)

    try:
        font_name = ImageFont.truetype("Roboto-Medium.ttf", size=int(21 * scale_x))
        font_upi = ImageFont.truetype("Roboto-Regular.ttf", size=int(13 * scale_x))
        font_ts = ImageFont.truetype("Roboto-Regular.ttf", size=int(14 * scale_x))
    except IOError:
        font_name = ImageFont.load_default()
        font_upi = ImageFont.load_default()
        font_ts = ImageFont.load_default()

    # Centered Timestamp
    formatted_ts = dt_obj.strftime("%d %B %Y at %I:%M %p").lstrip("0")
    _, _, tw, _ = draw.textbbox((0, 0), formatted_ts, font=font_ts)
    tx = (template.width - tw) / 2
    draw.text((tx, int(153 * scale_y)), formatted_ts, font=font_ts, fill=ts_color)

    # Name & UPI ID
    draw.text((int(138 * scale_x), int(214 * scale_y)), user_name, font=font_name, fill=name_color)
    draw.text((int(138 * scale_x), int(238 * scale_y)), upi_id, font=font_upi, fill=upi_color)

    return template

# --- CORE PROCESSING LOGIC ---

def process_mockup_job(creative: Image.Image, choice: str, color: str, base_name: str, 
                       pt_choice: str = None, dt_obj: datetime = None, user_name: str = None, upi_id: str = None):
    """Handles the entire workflow for generating a tagged creative and a mockup."""
    spec = PLACEMENT_SPECS[choice]

    if spec.get("type") == "multi-template-mockup":
        tmpl_info = spec["templates"][pt_choice]
        raw_coords = tmpl_info["mockup_coords"]
        mockup_file = tmpl_info["mockup_file"]
        theme = tmpl_info.get("theme", "light")
    else:
        raw_coords = spec["mockup_coords"]
        mockup_file = spec["mockup_file"]
        theme = "light"

    # 1. Ad Tag Application
    if color != "no ad tag":
        artboard_size = spec["tag_artboard_size"]
        tag_artboard_filename = f"tag_artboard_{color}_{artboard_size}.png"
        try:
            with Image.open(tag_artboard_filename) as tag_artboard:
                tag_artboard = tag_artboard.convert("RGBA")
                creative.paste(tag_artboard, (0, 0), tag_artboard)
        except FileNotFoundError:
            st.error(f"⚠️ **Error:** Ad Tag file not found: `{tag_artboard_filename}`.")
            return

    st.session_state.tagged_image_bytes = image_to_bytes(creative)
    tag_suffix = "AdTagged" if color != "no ad tag" else "NoTag"
    st.session_state.tagged_filename = f"{base_name}_{tag_suffix}.jpg"

    # 2. Create Mockup
    try:
        with Image.open(mockup_file) as template_image:
            template_image = template_image.convert("RGBA")
            
            if choice == "PT":
                scale_x = template_image.width / 512.0
                scale_y = template_image.height / 1024.0
                coords = [
                    int(raw_coords[0] * scale_x),
                    int(raw_coords[1] * scale_y),
                    int(raw_coords[2] * scale_x),
                    int(raw_coords[3] * scale_y)
                ]
                if dt_obj and user_name and upi_id:
                    template_image = render_pt_text(template_image, dt_obj, user_name, upi_id, theme=theme)
            else:
                scale_x = 1.0
                coords = raw_coords

            x1, y1, x2, y2 = coords
            slot_width, slot_height = x2 - x1, y2 - y1

            # Exact Slot Resizing (Zoom & Scale to Fill)
            final_creative = creative.resize((slot_width, slot_height), Image.Resampling.LANCZOS)
            final_creative = add_rounded_corners(final_creative, int(spec["radius"] * scale_x))
            
            template_image.paste(final_creative, (x1, y1), final_creative.getchannel('A'))

            clean_pt = pt_choice.replace(" ", "_") if pt_choice else ""
            mockup_name = f"{base_name}_{choice}_{clean_pt}_Screenshot.jpg" if pt_choice else f"{base_name}_{choice}_Screenshot.jpg"
            
            st.session_state.mockup_image_bytes = image_to_bytes(template_image)
            st.session_state.mockup_filename = mockup_name

            # 3. Create ZIP
            files_to_zip = {
                st.session_state.tagged_filename: st.session_state.tagged_image_bytes,
                st.session_state.mockup_filename: st.session_state.mockup_image_bytes
            }
            st.session_state.zip_bytes = create_zip_archive(files_to_zip)
            st.session_state.zip_filename = f"{base_name}_Mockup_Package.zip"

    except FileNotFoundError:
        st.error(f"⚠️ **Error:** Mockup template not found: `{mockup_file}`.")
        return

def process_overlay_job(creative: Image.Image, choice: str, base_name: str):
    """Handles the workflow for the overlay check."""
    spec = PLACEMENT_SPECS[choice]
    processed_image = creative 
    
    try:
        with Image.open(spec["overlay_file"]) as overlay_image:
            overlay_image = overlay_image.convert("RGBA")
            processed_image.paste(overlay_image, (0, 0), overlay_image)
            
        st.session_state.tagged_image_bytes = image_to_bytes(processed_image)
        st.session_state.tagged_filename = f"{base_name}_OverlapCheck.jpg"
        st.session_state.mockup_image_bytes = None
        st.session_state.zip_bytes = None
        
    except FileNotFoundError:
        st.error(f"⚠️ **Error:** Overlay file not found: `{spec['overlay_file']}`.")
        return

# --- STREAMLIT APP INTERFACE ---
st.set_page_config(page_title="Ad Tag & Mockup Generator", layout="wide")
st.title("🖼️ Ad Tag & Mockup Generator")
st.write("A simple tool to automate applying ad tags and creating mockups.")

# Initialize Session State
if 'tagged_image_bytes' not in st.session_state:
    st.session_state.tagged_image_bytes = None
    st.session_state.mockup_image_bytes = None
    st.session_state.zip_bytes = None

# --- SIDEBAR FOR USER INPUTS ---
with st.sidebar:
    st.write("Aditya - WIP")
    st.header("⚙️ Controls")
    uploaded_banner = st.file_uploader("1. Upload your banner creative", type=["jpg", "jpeg", "png"])
    template_choice = st.selectbox("2. Choose Job Type", list(PLACEMENT_SPECS.keys()))
    
    spec = PLACEMENT_SPECS[template_choice]
    pt_template_choice = None
    dt_combined = None
    user_name, upi_id = None, None

    if spec.get("type") == "multi-template-mockup":
        pt_templates = list(spec["templates"].keys())
        pt_template_choice = st.selectbox("3. Select PT Template & Mode", pt_templates)
        
        st.subheader("👤 User Details")
        user_name = st.text_input("Name", value="Akash PP")
        upi_id = st.text_input("UPI ID", value="akashb2307@oksbi")

        st.subheader("📅 Timestamp Settings")
        now_ist = datetime.now(ZoneInfo('Asia/Kolkata'))
        s_date = st.date_input("Date", now_ist.date())
        s_time = st.time_input("Time", now_ist.time())
        dt_combined = datetime.combine(s_date, s_time)

    ad_tag_color = None
    if spec["type"] in ["mockup", "multi-template-mockup"]:
        step_number = "4." if pt_template_choice else "3."
        ad_tag_color = st.selectbox(f"{step_number} Choose Ad Tag color", ["pink", "white", "no ad tag"])
        
    generate_button = st.button("🚀 Generate Now", use_container_width=True, type="primary")

# --- MAIN LOGIC & DISPLAY ---
if generate_button:
    if uploaded_banner:
        creative_image = Image.open(uploaded_banner).convert("RGBA")
        spec = PLACEMENT_SPECS[template_choice]
        job_type = spec["type"]
        
        actual_width, actual_height = creative_image.size
        expected_width, expected_height = (0, 0)
        
        if job_type in ["mockup", "multi-template-mockup"]:
            size_str = spec["tag_artboard_size"]
            expected_width, expected_height = map(int, size_str.split('x'))
        elif job_type == "overlay":
            expected_width, expected_height = spec["creative_size"]

        if (actual_width, actual_height) != (expected_width, expected_height):
            error_message = (
                f"**Dimension Mismatch!**\n\n"
                f"**Uploaded:** `{actual_width}x{actual_height}px`\n\n"
                f"**Required for '{template_choice}':** `{expected_width}x{expected_height}px`\n\n"
                "Please upload a creative with the correct dimensions."
            )
            st.error(error_message, icon="🚨")
        else:
            with st.spinner('Generating your assets... ✨'):
                base_filename = os.path.splitext(uploaded_banner.name)[0]
                
                if job_type in ["mockup", "multi-template-mockup"]:
                    process_mockup_job(
                        creative_image, 
                        template_choice, 
                        ad_tag_color, 
                        base_filename, 
                        pt_choice=pt_template_choice,
                        dt_obj=dt_combined,
                        user_name=user_name,
                        upi_id=upi_id
                    )
                elif job_type == "overlay":
                    process_overlay_job(creative_image, template_choice, base_filename)
                    
            st.rerun()
    else:
        st.sidebar.warning("☝️ Please upload a banner creative first!")

# --- DISPLAY RESULTS ---
if st.session_state.tagged_image_bytes:
    st.header("✅ Results")
    col1, col2 = st.columns(2)

    # Column 1: Tagged Creative
    with col1:
        header_col, button_col = st.columns([2, 1])
        with header_col:
            subheader_text = "1. Tagged Creative" if st.session_state.mockup_image_bytes else "1. Overlap Check"
            st.subheader(subheader_text)
        with button_col:
            st.download_button(
                label="⬇️ Download",
                data=st.session_state.tagged_image_bytes,
                file_name=st.session_state.get('tagged_filename', 'tagged.jpg'),
                mime="image/jpeg",
                use_container_width=True
            )
        st.image(st.session_state.tagged_image_bytes, use_container_width=True)

    # Column 2: Final Mockup (if present)
    with col2:
        if st.session_state.mockup_image_bytes:
            header_col, button_col = st.columns([2, 1])
            with header_col:
                st.subheader("2. Final Mockup")
            with button_col:
                st.download_button(
                    label="⬇️ Download",
                    data=st.session_state.mockup_image_bytes,
                    file_name=st.session_state.get('mockup_filename', 'mockup.jpg'),
                    mime="image/jpeg",
                    use_container_width=True
                )
            st.image(st.session_state.mockup_image_bytes, use_container_width=True)

    st.divider()

    # ZIP Download (if present)
    if st.session_state.zip_bytes:
        st.download_button(
            label="📦 Download Both as .zip",
            data=st.session_state.zip_bytes,
            file_name=st.session_state.get('zip_filename', 'package.zip'),
            mime="application/zip",
            use_container_width=True
        )
else:
    st.info("👋 Welcome! Please use the controls in the sidebar to get started.")
