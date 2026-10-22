import io
import os
import zipfile
from datetime import datetime
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
                "mockup_coords": [13, 428, 500, 812],  # Shifted top up to Y1=428 to close top gap
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

def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def create_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()

def render_pt_text(template: Image.Image, dt_obj: datetime, user_name: str, upi_id: str, theme: str = "light") -> Image.Image:
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

    # 1. Centered Timestamp
    formatted_ts = dt_obj.strftime("%d %B %Y at %I:%M %p").lstrip("0")
    _, _, tw, _ = draw.textbbox((0, 0), formatted_ts, font=font_ts)
    tx = (template.width - tw) / 2
    draw.text((tx, int(153 * scale_y)), formatted_ts, font=font_ts, fill=ts_color)

    # 2. Name & UPI ID
    draw.text((int(138 * scale_x), int(214 * scale_y)), user_name, font=font_name, fill=name_color)
    draw.text((int(138 * scale_x), int(238 * scale_y)), upi_id, font=font_upi, fill=upi_color)

    return template

# --- CORE ENGINE ---
def process_job(creative: Image.Image, choice: str, color: str, base_name: str, 
                pt_choice: str = None, dt_obj: datetime = None, user_name: str = None, upi_id: str = None):
    spec = PLACEMENT_SPECS[choice]
    
    if spec["type"] == "overlay":
        if os.path.exists(spec["overlay_file"]):
            with Image.open(spec["overlay_file"]) as overlay:
                creative.paste(overlay.convert("RGBA"), (0, 0), overlay.convert("RGBA"))
        st.session_state.tagged_bytes = image_to_bytes(creative)
        st.session_state.tagged_name = f"{base_name}_OverlapCheck.jpg"
        st.session_state.mockup_bytes = None
        st.session_state.zip_bytes = None
        return

    # Extract Specs
    if spec["type"] == "multi-template-mockup":
        tmpl_info = spec["templates"][pt_choice]
        raw_coords = tmpl_info["mockup_coords"]
        mockup_file = tmpl_info["mockup_file"]
        theme = tmpl_info.get("theme", "light")
    else:
        raw_coords = spec["mockup_coords"]
        mockup_file = spec["mockup_file"]
        theme = "light"

    if not os.path.exists(mockup_file):
        st.error(f"Mockup template `{mockup_file}` not found.")
        return

    # 1. Standalone Tagged Creative Export
    tagged_creative = creative.copy()
    if color != "no ad tag":
        tag_file = f"tag_artboard_{color}_{spec['tag_artboard_size']}.png"
        if os.path.exists(tag_file):
            with Image.open(tag_file) as tag:
                tagged_creative.paste(tag.convert("RGBA"), (0, 0), tag.convert("RGBA"))
        else:
            st.error(f"Ad Tag file `{tag_file}` not found.")
            return

    st.session_state.tagged_bytes = image_to_bytes(tagged_creative)
    tag_suffix = "AdTagged" if color != "no ad tag" else "NoTag"
    st.session_state.tagged_name = f"{base_name}_{tag_suffix}.jpg"

    # 2. Render Mockup with Exact Slot Resizing (Zoom/Scale to Fill)
    with Image.open(mockup_file) as tmpl:
        tmpl = tmpl.convert("RGBA")
        scale_x = tmpl.width / 512.0
        scale_y = tmpl.height / 1024.0
        
        coords = [
            int(raw_coords[0] * scale_x),
            int(raw_coords[1] * scale_y),
            int(raw_coords[2] * scale_x),
            int(raw_coords[3] * scale_y)
        ]
        
        if choice == "PT":
            tmpl = render_pt_text(tmpl, dt_obj, user_name, upi_id, theme=theme)

        x1, y1, x2, y2 = coords
        sw, sh = x2 - x1, y2 - y1

        # Zoom & Stretch to exact bounding box dimensions
        final_c = creative.resize((sw, sh), Image.Resampling.LANCZOS)

        # Apply Ad Tag layer post-resize to maintain exact tag scaling
        if color != "no ad tag":
            tag_file = f"tag_artboard_{color}_{spec['tag_artboard_size']}.png"
            if os.path.exists(tag_file):
                with Image.open(tag_file) as tag:
                    tag_resized = tag.resize(final_c.size, Image.Resampling.LANCZOS)
                    final_c.paste(tag_resized.convert("RGBA"), (0, 0), tag_resized.convert("RGBA"))

        final_c = add_rounded_corners(final_c, int(spec["radius"] * scale_x))
        tmpl.paste(final_c, (x1, y1), final_c.getchannel('A'))

        clean_pt = pt_choice.replace(" ", "_") if pt_choice else ""
        mockup_name = f"{base_name}_{choice}_{clean_pt}_Screenshot.jpg" if pt_choice else f"{base_name}_{choice}_Screenshot.jpg"
        st.session_state.mockup_bytes = image_to_bytes(tmpl)
        st.session_state.mockup_name = mockup_name

        st.session_state.zip_bytes = create_zip({
            st.session_state.tagged_name: st.session_state.tagged_bytes,
            st.session_state.mockup_name: st.session_state.mockup_bytes
        })
        st.session_state.zip_name = f"{base_name}_Mockup_Package.zip"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Ad Tag & Mockup Generator", layout="wide")
st.title("🖼️ Ad Tag & Mockup Generator")

for k in ['tagged_bytes', 'mockup_bytes', 'zip_bytes']:
    st.session_state.setdefault(k, None)

with st.sidebar:
    st.header("⚙️ Controls")
    banner = st.file_uploader("1. Banner Creative", type=["jpg", "jpeg", "png"])
    choice = st.selectbox("2. Job Type", list(PLACEMENT_SPECS.keys()))
    
    spec = PLACEMENT_SPECS[choice]
    pt_choice, dt_combined = None, None
    user_name, upi_id = None, None

    if spec.get("type") == "multi-template-mockup":
        pt_choice = st.selectbox("3. Select Template & Mode", list(spec["templates"].keys()))
        
        st.subheader("👤 User Details")
        user_name = st.text_input("Name", value="Akash PP")
        upi_id = st.text_input("UPI ID", value="akashb2307@oksbi")

        st.subheader("📅 Timestamp Settings")
        s_date = st.date_input("Date", datetime.now().date())
        s_time = st.time_input("Time", datetime.now().time())
        dt_combined = datetime.combine(s_date, s_time)

    color = None
    if spec["type"] in ["mockup", "multi-template-mockup"]:
        color = st.selectbox("Choose Ad Tag Color", ["pink", "white", "no ad tag"])

    run = st.button("🚀 Generate", type="primary", use_container_width=True)

if run:
    if banner:
        creative = Image.open(banner).convert("RGBA")
        req_w, req_h = map(int, spec["tag_artboard_size"].split('x')) if "tag_artboard_size" in spec else spec["creative_size"]
        
        if creative.size != (req_w, req_h):
            st.error(f"Dimension Mismatch! Uploaded: `{creative.size[0]}x{creative.size[1]}px`. Required: `{req_w}x{req_h}px`.")
        else:
            with st.spinner("Processing..."):
                base_name = os.path.splitext(banner.name)[0]
                process_job(creative, choice, color, base_name, pt_choice, dt_combined, user_name, upi_id)
            st.rerun()
    else:
        st.sidebar.warning("Please upload a file first.")

# --- DISPLAY OUTPUTS ---
if st.session_state.tagged_bytes:
    st.header("✅ Results")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. Tagged / Overlay")
        st.download_button("Download Image", st.session_state.tagged_bytes, st.session_state.tagged_name, "image/jpeg", use_container_width=True)
        st.image(st.session_state.tagged_bytes, use_container_width=True)
        
    with c2:
        if st.session_state.mockup_bytes:
            st.subheader("2. Final Mockup")
            st.download_button("Download Mockup", st.session_state.mockup_bytes, st.session_state.mockup_name, "image/jpeg", use_container_width=True)
            st.image(st.session_state.mockup_bytes, use_container_width=True)

    if st.session_state.zip_bytes:
        st.divider()
        st.download_button("📦 Download Package (.zip)", st.session_state.zip_bytes, st.session_state.zip_name, "application/zip", use_container_width=True)