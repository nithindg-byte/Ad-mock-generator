import io
import math
import os
import tempfile
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- UNIFIED CONFIGURATION DATABASE ---
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
            "Light": {
                "mockup_file": "Parking_Light.png",
                "mockup_coords": [13, 428, 500, 812],
                "theme": "light"
            },
            "Dark": {
                "mockup_file": "Parking_Dark.png",
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
    },
    "Swipe Up": {
        "type": "sequence-mockup",
        "tag_artboard_size": "6x5",
        "templates": {
            "Template 1 (Resting)": {
                "file": "template_1",
                "coords": [23, 615, 517, 1043],
                "radius": 19,
                "mode": "fit_exact",
            },
            "Template 2 (Touch State)": {
                "file": "template_2",
                "coords": [23, 645, 517, 1073],
                "radius": 20,
                "mode": "fit_exact",
            },
            "Template 3 (Touch Start)": {
                "file": "template_3",
                "coords": [23, 615, 517, 1043],
                "radius": 20,
                "mode": "fit_exact",
            },
            "Template 4 (Micro-lift)": {
                "file": "template_4",
                "coords": [23, 640, 517, 1068],
                "radius": 20,
                "mode": "fit_exact",
            },
            "Template 5 (Ascending)": {
                "file": "template_5",
                "coords": [23, 615, 517, 1043],
                "radius": 20,
                "mode": "fit_exact",
            },
            "Template 6 (Upward Motion)": {
                "file": "template_6",
                "coords": [23, 544, 517, 972],
                "radius": 20,
                "mode": "fit_exact",
            },
            "Template 7 (Sheet Pull-up)": {
                "file": "template_7",
                "coords": [15, 334, 525, 558],
                "radius": 16,
                "mode": "sheet_crop",
            },
            "Template 8 (Full Screen Ad)": {
                "file": "template_8",
                "coords": [0, 0, 540, 1200],
                "radius": 0,
                "mode": "fullscreen",
            },
        },
    }
}

# --- COMMON UTILITIES ---

def hex_to_rgb(hex_str: str, default: tuple = (255, 255, 255)) -> tuple:
    """Converts a hex color code (#RRGGBB or #RGB) to an (R, G, B) tuple."""
    hex_clean = hex_str.strip().lstrip("#")
    try:
        if len(hex_clean) == 3:
            hex_clean = "".join([c * 2 for c in hex_clean])
        if len(hex_clean) == 6:
            return tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        pass
    return default

def get_font(font_name: str, size: int):
    """Safely locates and loads TrueType fonts from root, assets, or system paths."""
    search_paths = [
        os.path.join(BASE_DIR, font_name),
        os.path.join(BASE_DIR, "assets", font_name),
        os.getcwd(),
        os.path.join(os.getcwd(), "assets", font_name),
        os.path.join(r"C:\Windows\Fonts", font_name),
    ]
    for p in search_paths:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    try:
        return ImageFont.truetype(font_name, size=size)
    except Exception:
        return ImageFont.load_default()

def add_rounded_corners(im: Image.Image, rad: int, top_only: bool = False) -> Image.Image:
    """Applies clean rounded corners via an alpha mask."""
    if rad <= 0:
        return im
    circle = Image.new("L", (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2 - 1, rad * 2 - 1), fill=255)

    alpha = Image.new("L", im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))

    if not top_only:
        alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
        alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))

    im.putalpha(alpha)
    return im

def image_to_bytes(image: Image.Image) -> bytes:
    """Saves a PIL image to an in-memory bytes buffer as a JPEG."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()

def create_zip_archive(files_to_zip: dict) -> bytes:
    """Creates a zip archive from a dictionary of filenames and byte content."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename, data in files_to_zip.items():
            zipf.writestr(filename, data)
    return zip_buf.getvalue()

def load_file_auto(filename_base: str) -> Image.Image:
    """Finds image template checking root directory and assets/ subfolder."""
    search_dirs = [
        BASE_DIR,
        os.path.join(BASE_DIR, "assets"),
        os.getcwd(),
        os.path.join(os.getcwd(), "assets"),
    ]
    extensions = ["jpg", "png", "jpeg", "webp", "JPG", "PNG", "JPEG"]

    for d in search_dirs:
        direct = os.path.join(d, filename_base)
        if os.path.isfile(direct):
            return Image.open(direct).convert("RGBA")
        for ext in extensions:
            candidate = os.path.join(d, f"{filename_base}.{ext}")
            if os.path.isfile(candidate):
                return Image.open(candidate).convert("RGBA")
    return None

# --- TEXT RENDERING FOR PT STATIC MOCKUPS ---

def render_pt_text(template: Image.Image, dt_obj: datetime, user_name: str, upi_id: str, amount: str, theme: str = "light") -> Image.Image:
    """Renders user metadata, bold amount, and formatted timestamp directly onto standard PT templates."""
    draw = ImageDraw.Draw(template)

    scale_x = template.width / 512.0
    scale_y = template.height / 1024.0

    if theme == "dark":
        name_color = (255, 255, 255)
        upi_color = (154, 160, 166)
        amount_color = (255, 255, 255)
    else:
        name_color = (32, 33, 36)
        upi_color = (95, 99, 104)
        amount_color = (32, 33, 36)

    ts_color = (213, 227, 200)

    try:
        font_name = ImageFont.truetype("Roboto-Medium.ttf", size=int(21 * scale_x))
    except IOError:
        font_name = ImageFont.load_default()

    try:
        font_upi = ImageFont.truetype("Roboto-Regular.ttf", size=int(13 * scale_x))
    except IOError:
        font_upi = ImageFont.load_default()

    try:
        font_amount = ImageFont.truetype("Roboto-Bold.ttf", size=int(24 * scale_x))
        amount_stroke = 0
    except IOError:
        try:
            font_amount = ImageFont.truetype("Roboto-Regular.ttf", size=int(24 * scale_x))
            amount_stroke = max(1, int(1 * scale_x))
        except IOError:
            font_amount = ImageFont.load_default()
            amount_stroke = 0

    try:
        font_ts = ImageFont.truetype("Roboto-Regular.ttf", size=int(14 * scale_x))
    except IOError:
        font_ts = ImageFont.load_default()

    formatted_ts = dt_obj.strftime("%d %B %Y at %I:%M %p").lstrip("0")
    _, _, tw, _ = draw.textbbox((0, 0), formatted_ts, font=font_ts)
    tx = (template.width - tw) / 2
    draw.text((tx, int(153 * scale_y)), formatted_ts, font=font_ts, fill=ts_color)

    draw.text((int(138 * scale_x), int(214 * scale_y)), user_name, font=font_name, fill=name_color)
    draw.text((int(138 * scale_x), int(238 * scale_y)), upi_id, font=font_upi, fill=upi_color)

    formatted_amount = amount if amount.startswith("₹") else f"₹{amount}"
    draw.text(
        (int(138 * scale_x), int(262 * scale_y)),
        formatted_amount,
        font=font_amount,
        fill=amount_color,
        stroke_width=amount_stroke,
        stroke_fill=amount_color
    )

    return template

# --- CORE LOGIC: STATIC MOCKUPS & OVERLAYS ---

def process_mockup_job(creative: Image.Image, choice: str, color: str, base_name: str, 
                       pt_choice: str = None, dt_obj: datetime = None, user_name: str = None, upi_id: str = None, amount: str = None):
    """Handles workflow for standard mockups (RewardsATF, PT, CBB, CBC)."""
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

    # Ad Tag Application
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

    # Mockup Construction
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
                if dt_obj and user_name and upi_id and amount:
                    template_image = render_pt_text(template_image, dt_obj, user_name, upi_id, amount, theme=theme)
            else:
                scale_x = 1.0
                coords = raw_coords

            x1, y1, x2, y2 = coords
            slot_width, slot_height = x2 - x1, y2 - y1

            final_creative = creative.resize((slot_width, slot_height), Image.Resampling.LANCZOS)
            final_creative = add_rounded_corners(final_creative, int(spec["radius"] * scale_x))
            
            template_image.paste(final_creative, (x1, y1), final_creative.getchannel('A'))

            clean_pt = pt_choice.replace(" ", "_") if pt_choice else ""
            mockup_name = f"{base_name}_{choice}_{clean_pt}_Screenshot.jpg" if pt_choice else f"{base_name}_{choice}_Screenshot.jpg"
            
            st.session_state.mockup_image_bytes = image_to_bytes(template_image)
            st.session_state.mockup_filename = mockup_name

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
    """Handles workflow for Coupon overlay check."""
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

# --- ANIMATION & SWIPE-UP ENGINE HELPERS ---

def apply_bottom_fadeout(card_img: Image.Image, rad: int) -> Image.Image:
    """Overlays a dark gradient fadeout on the bottom portion of the card."""
    cw, ch = card_img.size
    fade_h = int(ch * 0.35)
    fade_overlay = Image.new("RGBA", (cw, fade_h), (0, 0, 0, 0))

    for y in range(fade_h):
        ratio = y / max(1, fade_h - 1)
        alpha = int((ratio**1.3) * 235)
        for x in range(cw):
            fade_overlay.putpixel((x, y), (14, 14, 16, alpha))

    card_img.paste(fade_overlay, (0, ch - fade_h), fade_overlay)
    return add_rounded_corners(card_img, rad, top_only=False)

def render_user_details(template: Image.Image, dt_obj: datetime, user_name: str, upi_id: str, amount: str) -> Image.Image:
    """Renders user transaction details onto Templates 1 to 6 for the Swipe Up sequence."""
    draw = ImageDraw.Draw(template)

    scale_x = template.width / 540.0
    scale_y = template.height / 1200.0

    sample_pt = (int(30 * scale_x), int(250 * scale_y))
    exact_bg_green = template.getpixel(sample_pt)

    draw.rectangle([int(50 * scale_x), int(238 * scale_y), int(490 * scale_x), int(264 * scale_y)], fill=exact_bg_green)
    draw.rectangle([int(135 * scale_x), int(305 * scale_y), int(405 * scale_x), int(395 * scale_y)], fill=(25, 25, 27, 255))

    av_x1, av_y1 = int(42 * scale_x), int(310 * scale_y)
    av_x2, av_y2 = int(118 * scale_x), int(386 * scale_y)
    draw.rounded_rectangle([av_x1, av_y1, av_x2, av_y2], radius=int(20 * scale_x), fill=(47, 163, 240, 255))

    font_name = get_font("Roboto-Medium.ttf", int(19 * scale_x))
    font_upi = get_font("Roboto-Regular.ttf", int(13 * scale_x))
    font_ts = get_font("Roboto-Regular.ttf", int(12 * scale_x))
    font_amt = get_font("Roboto-Medium.ttf", int(22 * scale_x))
    font_avatar = get_font("Roboto-Medium.ttf", int(26 * scale_x))

    ts_color = (210, 232, 206)
    name_color = (255, 255, 255)
    upi_color = (158, 163, 168)
    amt_color = (255, 255, 255)
    av_color = (255, 255, 255)

    formatted_ts = dt_obj.strftime("%d %B %Y at %I:%M %p").lstrip("0")
    bbox_ts = draw.textbbox((0, 0), formatted_ts, font=font_ts)
    tw_ts = bbox_ts[2] - bbox_ts[0]
    tx_ts = (template.width - tw_ts) / 2
    draw.text((tx_ts, int(246 * scale_y)), formatted_ts, font=font_ts, fill=ts_color)

    name_clean = user_name.strip()
    parts = name_clean.split()
    if len(parts) >= 2:
        initials = (parts[0][0] + parts[-1][0]).upper()
    elif len(name_clean) >= 2:
        initials = name_clean[:2].upper()
    else:
        initials = name_clean.upper()

    bbox_av = draw.textbbox((0, 0), initials, font=font_avatar)
    aw = bbox_av[2] - bbox_av[0]
    ah = bbox_av[3] - bbox_av[1]
    ax = av_x1 + ((av_x2 - av_x1) - aw) // 2
    ay = av_y1 + ((av_y2 - av_y1) - ah) // 2 - int(2 * scale_y)
    draw.text((ax, ay), initials, font=font_avatar, fill=av_color)

    draw.text((int(145 * scale_x), int(312 * scale_y)), user_name, font=font_name, fill=name_color)
    draw.text((int(145 * scale_x), int(340 * scale_y)), upi_id, font=font_upi, fill=upi_color)

    formatted_amount = amount if amount.startswith("₹") else f"₹{amount}"
    draw.text((int(145 * scale_x), int(368 * scale_y)), formatted_amount, font=font_amt, fill=amt_color)

    return template

def overlay_template8_decorations(
    t8_img: Image.Image,
    cta_text: str = "APPLY NOW",
    cta_text_color_hex: str = "#2488A6",
    cta_bg_color_hex: str = "#FFFFFF",
    cta_stroke_color_hex: str = "#FFFFFF",
    cta_stroke_width: int = 0,
) -> Image.Image:
    """Overlays top-right close 'X' button and optional bottom CTA button on Template 8."""
    img = t8_img.convert("RGBA")
    w, h = img.size
    scale_x = w / 540.0
    scale_y = h / 1200.0

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top-Right Close Button
    btn_radius = int(21 * scale_x)
    center_x = int(496 * scale_x)
    center_y = int(92 * scale_y)

    draw.ellipse(
        [center_x - btn_radius, center_y - btn_radius, center_x + btn_radius, center_y + btn_radius],
        fill=(30, 30, 30, 185),
    )

    x_size = int(8.5 * scale_x)
    x_thickness = max(2, int(2.2 * scale_x))
    white_color = (255, 255, 255, 245)

    draw.line([(center_x - x_size, center_y - x_size), (center_x + x_size, center_y + x_size)], fill=white_color, width=x_thickness)
    draw.line([(center_x - x_size, center_y + x_size), (center_x + x_size, center_y - x_size)], fill=white_color, width=x_thickness)

    # Bottom CTA Button
    cta_text_clean = (cta_text or "").strip()
    if cta_text_clean:
        cta_x1 = int(20 * scale_x)
        cta_y1 = int(1060 * scale_y)
        cta_x2 = int(520 * scale_x)
        cta_y2 = int(1140 * scale_y)
        cta_w = cta_x2 - cta_x1
        cta_h = cta_y2 - cta_y1
        corner_rad = int(15 * scale_x)

        cta_text_rgb = hex_to_rgb(cta_text_color_hex, default=(36, 136, 166))
        cta_stroke_rgb = hex_to_rgb(cta_stroke_color_hex, default=(255, 255, 255))
        cta_bg_rgb = hex_to_rgb(cta_bg_color_hex, default=(255, 255, 255))
        scaled_stroke_width = int(cta_stroke_width * scale_x)

        draw.rounded_rectangle(
            [cta_x1, cta_y1, cta_x2, cta_y2],
            radius=corner_rad,
            fill=cta_bg_rgb + (255,),
            outline=cta_stroke_rgb + (255,) if scaled_stroke_width > 0 else None,
            width=scaled_stroke_width,
        )

        font_cta = get_font("Roboto-Medium.ttf", int(16 * scale_x)) or get_font("Roboto-Regular.ttf", int(16 * scale_x))
        tracking_px = int(1.8 * scale_x)
        char_widths = [draw.textbbox((0, 0), ch, font=font_cta)[2] - draw.textbbox((0, 0), ch, font=font_cta)[0] for ch in cta_text_clean]
        sample_bbox = draw.textbbox((0, 0), "A", font=font_cta)
        txt_h = sample_bbox[3] - sample_bbox[1]
        total_txt_w = sum(char_widths) + (len(cta_text_clean) - 1) * tracking_px

        start_x = cta_x1 + (cta_w - total_txt_w) // 2
        txt_y = cta_y1 + (cta_h - txt_h) // 2 - int(2 * scale_y)

        curr_x = start_x
        for idx, ch in enumerate(cta_text_clean):
            draw.text((curr_x, txt_y), ch, font=font_cta, fill=cta_text_rgb + (255,))
            curr_x += char_widths[idx] + tracking_px

    return Image.alpha_composite(img, overlay)

def ease_in_out_sine(x: float) -> float:
    return -(math.cos(math.pi * x) - 1.0) / 2.0

def ease_out_cubic(x: float) -> float:
    return 1.0 - math.pow(1.0 - x, 3)

def render_html_animation_frames(
    html_content: str, duration_sec: float = 3.6, fps: int = 30, width: int = 540, height: int = 1200
) -> list[Image.Image]:
    """Renders HTML animation using local browser via Playwright."""
    from playwright.sync_api import sync_playwright

    total_frames = int(duration_sec * fps)
    captured_frames = []

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_content)
        temp_html_path = f.name

    try:
        with sync_playwright() as p:
            browser = None
            for browser_channel in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch(headless=True, channel=browser_channel)
                    break
                except Exception:
                    continue

            if browser is None:
                raise RuntimeError("Could not find an installed Google Chrome or Microsoft Edge on this computer.")

            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file://{os.path.abspath(temp_html_path)}")
            page.wait_for_load_state("networkidle")

            step_ms = 1000.0 / fps
            for _ in range(total_frames):
                screenshot_bytes = page.screenshot(type="png")
                frame_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
                captured_frames.append(frame_img)
                page.wait_for_timeout(step_ms)

            browser.close()
    finally:
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

    return captured_frames

def generate_smooth_video(
    frames_dict: dict,
    sheet_container_crop: Image.Image,
    clean_bg_without_sheet: Image.Image,
    sheet_crop_top: int,
    dip_delta: int,
    done_footer_crop: Image.Image,
    done_footer_top: int,
    t8_animated_frames: list[Image.Image] = None,
    fps: int = 30,
    total_duration: float = 6.0,
) -> tuple[bytes, str]:
    """Compiles sequence video matching native swipe physics and decorated Template 8."""
    keys = list(frames_dict.keys())
    t6 = frames_dict[keys[5]].convert("RGBA")
    t7 = frames_dict[keys[6]].convert("RGBA")
    t8 = frames_dict[keys[7]].convert("RGBA")

    w, h = clean_bg_without_sheet.size
    if w % 2 != 0:
        w -= 1
    if h % 2 != 0:
        h -= 1

    video_frames = []
    current_frame_idx = 0

    def append_raw_frame(img: Image.Image):
        nonlocal current_frame_idx
        final_rgb = img.convert("RGB").resize((w, h))
        video_frames.append(np.array(final_rgb))
        current_frame_idx += 1

    def render_translated_sheet(y_offset: int) -> Image.Image:
        frame = clean_bg_without_sheet.copy()
        frame.paste(sheet_container_crop, (0, sheet_crop_top + y_offset), sheet_container_crop.getchannel("A"))
        if done_footer_crop:
            frame.paste(done_footer_crop, (0, done_footer_top), done_footer_crop.getchannel("A"))
        return frame

    total_target_frames = int(total_duration * fps)

    # 1. Initial Resting hold
    for _ in range(10):
        append_raw_frame(render_translated_sheet(0))

    # 2. Dip 1
    step1_down = 8
    for i in range(step1_down):
        alpha = ease_in_out_sine((i + 1) / float(step1_down))
        curr_offset = int(dip_delta * alpha)
        append_raw_frame(render_translated_sheet(curr_offset))

    for _ in range(6):
        append_raw_frame(render_translated_sheet(dip_delta))

    # 3. Lift 1
    step2_up = 9
    for i in range(step2_up):
        alpha = ease_in_out_sine((i + 1) / float(step2_up))
        curr_offset = int(dip_delta * (1.0 - alpha))
        append_raw_frame(render_translated_sheet(curr_offset))

    # 4. Dip 2
    step3_down = 8
    for i in range(step3_down):
        alpha = ease_in_out_sine((i + 1) / float(step3_down))
        curr_offset = int(dip_delta * alpha)
        append_raw_frame(render_translated_sheet(curr_offset))

    for _ in range(6):
        append_raw_frame(render_translated_sheet(dip_delta))

    # 5. Lift 2
    step4_up = 9
    for i in range(step4_up):
        alpha = ease_in_out_sine((i + 1) / float(step4_up))
        curr_offset = int(dip_delta * (1.0 - alpha))
        append_raw_frame(render_translated_sheet(curr_offset))

    # 6. Dip 3
    step5_down = 8
    for i in range(step5_down):
        alpha = ease_in_out_sine((i + 1) / float(step5_down))
        curr_offset = int(dip_delta * alpha)
        append_raw_frame(render_translated_sheet(curr_offset))

    for _ in range(5):
        append_raw_frame(render_translated_sheet(dip_delta))

    # 7. Launch into T6
    launch_frames = 10
    t5_launch = render_translated_sheet(0)
    for i in range(launch_frames):
        prog = (i + 1) / float(launch_frames)
        eased = ease_out_cubic(prog)
        append_raw_frame(Image.blend(t5_launch, t6, eased))

    # 8. Transition into T7
    to_t7_frames = 2
    for i in range(to_t7_frames):
        prog = (i + 1) / float(to_t7_frames)
        eased = ease_out_cubic(prog)
        append_raw_frame(Image.blend(t6, t7, eased))

    append_raw_frame(t7)

    # 9. Full Screen Ad
    remaining_frames = max(1, total_target_frames - current_frame_idx)
    if t8_animated_frames and len(t8_animated_frames) > 0:
        for idx in range(remaining_frames):
            frame_to_use = t8_animated_frames[idx % len(t8_animated_frames)]
            append_raw_frame(frame_to_use)
    else:
        for _ in range(remaining_frames):
            append_raw_frame(t8)

    temp_dir = tempfile.gettempdir()
    video_path = os.path.join(temp_dir, "phonepe_smooth_ad.mp4")

    iio.imwrite(video_path, video_frames, fps=fps, codec="libx264")

    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    return video_bytes, "phonepe_smooth_ad.mp4"

def process_sequence_job(
    banner_img: Image.Image,
    fullscreen_img: Image.Image,
    base_name: str,
    t8_animated_frames: list[Image.Image] = None,
    dt_obj: datetime = None,
    user_name: str = None,
    upi_id: str = None,
    amount: str = None,
    cta_text: str = "APPLY NOW",
    cta_text_color: str = "#2488A6",
    cta_bg_color: str = "#FFFFFF",
    cta_stroke_color: str = "#FFFFFF",
    cta_stroke_width: int = 0,
):
    """Processes sequence workflow for the 'Swipe Up' option."""
    spec = PLACEMENT_SPECS["Swipe Up"]
    templates_dict = spec["templates"]
    generated_screens = {}
    pil_frames_dict = {}
    files_to_zip = {}

    sheet_container_crop = None
    clean_bg_without_sheet = None
    done_footer_crop = None
    done_footer_top = 0
    sheet_crop_top = 0
    dip_delta = 30

    decorated_t8_animated_frames = None
    if t8_animated_frames and len(t8_animated_frames) > 0:
        decorated_t8_animated_frames = [
            overlay_template8_decorations(
                f,
                cta_text=cta_text,
                cta_text_color_hex=cta_text_color,
                cta_bg_color_hex=cta_bg_color,
                cta_stroke_color_hex=cta_stroke_color,
                cta_stroke_width=cta_stroke_width,
            )
            for f in t8_animated_frames
        ]

    for idx, (tmpl_label, tmpl_info) in enumerate(templates_dict.items(), 1):
        tmpl_file = tmpl_info["file"]
        template_image = load_file_auto(tmpl_file)

        if template_image is None:
            st.error(f"⚠️ Template file `{tmpl_file}` not found.")
            return

        raw_coords = tmpl_info["coords"]
        raw_rad = tmpl_info["radius"]
        mode = tmpl_info["mode"]

        scale_x = template_image.width / 540.0
        scale_y = template_image.height / 1200.0

        coords = [
            int(raw_coords[0] * scale_x),
            int(raw_coords[1] * scale_y),
            int(raw_coords[2] * scale_x),
            int(raw_coords[3] * scale_y),
        ]
        rad = int(raw_rad * scale_x)
        x1, y1, x2, y2 = coords
        slot_width, slot_height = x2 - x1, y2 - y1

        if dt_obj and user_name and upi_id and amount and idx <= 6:
            template_image = render_user_details(template_image, dt_obj, user_name, upi_id, amount)

        if mode == "fit_exact":
            fitted = ImageOps.fit(
                banner_img.convert("RGBA"),
                (slot_width, slot_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            final_card = add_rounded_corners(fitted, rad, top_only=False)
            if idx <= 6:
                final_card = apply_bottom_fadeout(final_card, rad)

            template_image.paste(final_card, (x1, y1), final_card.getchannel("A"))

            if idx == 1:
                sheet_crop_top = y1 - int(32 * scale_y)
                sheet_crop_bottom = y2 + int(35 * scale_y)

                sheet_container_crop = template_image.crop(
                    (0, sheet_crop_top, template_image.width, sheet_crop_bottom)
                ).convert("RGBA")

                done_footer_top = y2 + int(35 * scale_y)
                done_footer_crop = template_image.crop(
                    (0, done_footer_top, template_image.width, template_image.height)
                ).convert("RGBA")

                clean_bg_without_sheet = template_image.copy()
                bg_draw = ImageDraw.Draw(clean_bg_without_sheet)
                sample_dark_bg = template_image.getpixel((int(25 * scale_x), max(0, sheet_crop_top - 6)))

                if len(sample_dark_bg) == 4 and sample_dark_bg[3] == 0:
                    sample_dark_bg = (22, 22, 24, 255)
                elif len(sample_dark_bg) == 3:
                    sample_dark_bg = (sample_dark_bg[0], sample_dark_bg[1], sample_dark_bg[2], 255)

                bg_draw.rectangle([0, sheet_crop_top, template_image.width, done_footer_top], fill=sample_dark_bg)

            elif idx == 2:
                dip_delta = y1 - int(615 * scale_y)

            if idx <= 6 and done_footer_crop:
                template_image.paste(done_footer_crop, (0, done_footer_top), done_footer_crop.getchannel("A"))

        elif mode == "sheet_crop":
            ref_height = int(412 * scale_y)
            fitted_full = ImageOps.fit(
                banner_img.convert("RGBA"),
                (slot_width, ref_height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.0),
            )
            sheet_slice = fitted_full.crop((0, 0, slot_width, slot_height))
            final_card = add_rounded_corners(sheet_slice, rad, top_only=True)
            template_image.paste(final_card, (x1, y1), final_card.getchannel("A"))

        elif mode == "fullscreen":
            template_image = ImageOps.fit(
                fullscreen_img.convert("RGBA"),
                (template_image.width, template_image.height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            template_image = overlay_template8_decorations(
                template_image,
                cta_text=cta_text,
                cta_text_color_hex=cta_text_color,
                cta_bg_color_hex=cta_bg_color,
                cta_stroke_color_hex=cta_stroke_color,
                cta_stroke_width=cta_stroke_width,
            )

        pil_frames_dict[tmpl_label] = template_image.copy()

        screen_bytes = image_to_bytes(template_image)
        screen_filename = f"{base_name}_Screen_{idx}.jpg"
        generated_screens[tmpl_label] = (screen_bytes, screen_filename)
        files_to_zip[screen_filename] = screen_bytes

    vid_bytes, vid_filename = generate_smooth_video(
        pil_frames_dict,
        sheet_container_crop=sheet_container_crop,
        clean_bg_without_sheet=clean_bg_without_sheet,
        sheet_crop_top=sheet_crop_top,
        dip_delta=dip_delta,
        done_footer_crop=done_footer_crop,
        done_footer_top=done_footer_top,
        t8_animated_frames=decorated_t8_animated_frames,
        fps=30,
        total_duration=6.0,
    )
    files_to_zip[vid_filename] = vid_bytes

    st.session_state.video_bytes = vid_bytes
    st.session_state.video_filename = f"{base_name}_Smooth_Animation.mp4"
    st.session_state.sequence_screens = generated_screens
    st.session_state.zip_bytes = create_zip_archive(files_to_zip)
    st.session_state.zip_filename = f"{base_name}_Sequence_Templates.zip"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Ad Tag & Mockup Generator", layout="wide")
st.title("🖼️ Ad Tag, Mockup & Animation Generator")

# Initialize Session State
for key in ["tagged_image_bytes", "mockup_image_bytes", "zip_bytes", "video_bytes", "sequence_screens"]:
    if key not in st.session_state:
        st.session_state[key] = None

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("⚙️ Controls")
    
    # 1. Creative Upload
    uploaded_banner = st.file_uploader("1. Upload Banner Creative", type=["jpg", "jpeg", "png"])
    
    # 2. Choose Job Type
    template_choice = st.selectbox("2. Choose Job Type", list(PLACEMENT_SPECS.keys()))
    spec = PLACEMENT_SPECS[template_choice]
    job_type = spec["type"]

    # Dynamic variables
    pt_template_choice = None
    uploaded_fullscreen = None
    ad_tag_color = None
    user_name, upi_id, amount_val = "Akash PP", "akashb2307@oksbi", "1"
    dt_combined = None
    cta_text, cta_text_color, cta_bg_color, cta_stroke_color, cta_stroke_width = "APPLY NOW", "#2488A6", "#FFFFFF", "#FFFFFF", 0

    # Branch 1: PT Static Mockup Options
    if job_type == "multi-template-mockup":
        pt_templates = list(spec["templates"].keys())
        pt_template_choice = st.selectbox("3. Select PT Template & Mode", pt_templates)
        
        st.subheader("👤 User Details")
        user_name = st.text_input("Name", value="Akash PP")
        upi_id = st.text_input("UPI ID", value="akashb2307@oksbi")
        amount_val = st.text_input("Amount", value="1")

        st.subheader("📅 Timestamp Settings")
        now_ist = datetime.now(ZoneInfo('Asia/Kolkata'))
        s_date = st.date_input("Date", now_ist.date())
        s_time = st.time_input("Time", now_ist.time())
        dt_combined = datetime.combine(s_date, s_time)

        ad_tag_color = st.selectbox("4. Choose Ad Tag color", ["pink", "white", "no ad tag"])

    # Branch 2: Standard Static Mockups
    elif job_type == "mockup":
        ad_tag_color = st.selectbox("3. Choose Ad Tag color", ["pink", "white", "no ad tag"])

    # Branch 3: Swipe Up (Animation Sequence)
    elif job_type == "sequence-mockup":
        uploaded_fullscreen = st.file_uploader(
            "3. Upload Full-Screen Ad / HTML Animation (Template 8)",
            type=["jpg", "jpeg", "png", "html", "htm", "txt"],
        )

        st.subheader("👤 User Details")
        user_name = st.text_input("Name", value="Akash PP")
        upi_id = st.text_input("UPI ID", value="akashb2307@oksbi")
        amount_val = st.text_input("Amount", value="₹25")

        st.subheader("📅 Timestamp Settings")
        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        s_date = st.date_input("Date", now_ist.date())
        s_time = st.time_input("Time", now_ist.time())
        dt_combined = datetime.combine(s_date, s_time)

        st.subheader("🔘 Template 8 CTA Button Customizer")
        st.caption("Leave 'CTA Text' blank if you do not want any bottom CTA button.")
        cta_text = st.text_input("CTA Text", value="APPLY NOW")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            cta_text_color = st.text_input("Text Color (Hex)", value="#2488A6")
            cta_bg_color = st.text_input("Background Color (Hex)", value="#FFFFFF")
        with col_c2:
            cta_stroke_color = st.text_input("Stroke Color (Hex)", value="#FFFFFF")
            cta_stroke_width = st.slider("Stroke Weight (px)", min_value=0, max_value=8, value=0)

    generate_button = st.button("🚀 Generate Now", use_container_width=True, type="primary")

# --- EXECUTION ENGINE ---
if generate_button:
    if uploaded_banner:
        creative_image = Image.open(uploaded_banner).convert("RGBA")
        base_filename = os.path.splitext(uploaded_banner.name)[0]
        actual_width, actual_height = creative_image.size

        # Reset active session state
        st.session_state.tagged_image_bytes = None
        st.session_state.mockup_image_bytes = None
        st.session_state.video_bytes = None
        st.session_state.sequence_screens = None
        st.session_state.zip_bytes = None

        if job_type in ["mockup", "multi-template-mockup"]:
            size_str = spec["tag_artboard_size"]
            expected_width, expected_height = map(int, size_str.split('x'))

            if (actual_width, actual_height) != (expected_width, expected_height):
                st.error(
                    f"🚨 **Dimension Mismatch!**\n\n"
                    f"**Uploaded:** `{actual_width}x{actual_height}px`\n\n"
                    f"**Required for '{template_choice}':** `{expected_width}x{expected_height}px`\n\n"
                    "Please upload a creative with the correct dimensions."
                )
            else:
                with st.spinner('Generating mockups... ✨'):
                    process_mockup_job(
                        creative_image,
                        template_choice,
                        ad_tag_color,
                        base_filename,
                        pt_choice=pt_template_choice,
                        dt_obj=dt_combined,
                        user_name=user_name,
                        upi_id=upi_id,
                        amount=amount_val
                    )
                st.rerun()

        elif job_type == "overlay":
            expected_width, expected_height = spec["creative_size"]
            if (actual_width, actual_height) != (expected_width, expected_height):
                st.error(
                    f"🚨 **Dimension Mismatch!**\n\n"
                    f"**Uploaded:** `{actual_width}x{actual_height}px`\n\n"
                    f"**Required for '{template_choice}':** `{expected_width}x{expected_height}px`\n\n"
                    "Please upload a creative with the correct dimensions."
                )
            else:
                with st.spinner('Checking overlay... ✨'):
                    process_overlay_job(creative_image, template_choice, base_filename)
                st.rerun()

        elif job_type == "sequence-mockup":
            if not uploaded_fullscreen:
                st.sidebar.error("☝️ Please upload the Full-Screen Ad or HTML Animation file!")
            else:
                ext = os.path.splitext(uploaded_fullscreen.name)[1].lower()
                is_html = ext in [".html", ".htm", ".txt"]
                t8_animated_frames = None

                if is_html:
                    html_content = uploaded_fullscreen.read().decode("utf-8", errors="ignore")
                    with st.spinner("Rendering HTML animation frames via local browser... 🌐✨"):
                        t8_animated_frames = render_html_animation_frames(
                            html_content, duration_sec=3.6, fps=30, width=540, height=1200
                        )
                    fullscreen_image = t8_animated_frames[0]
                else:
                    fullscreen_image = Image.open(uploaded_fullscreen).convert("RGBA")

                with st.spinner("Rendering Crisp Video & Sequence Mockups... 🎬✨"):
                    process_sequence_job(
                        creative_image,
                        fullscreen_image,
                        base_filename,
                        t8_animated_frames=t8_animated_frames,
                        dt_obj=dt_combined,
                        user_name=user_name,
                        upi_id=upi_id,
                        amount=amount_val,
                        cta_text=cta_text,
                        cta_text_color=cta_text_color,
                        cta_bg_color=cta_bg_color,
                        cta_stroke_color=cta_stroke_color,
                        cta_stroke_width=cta_stroke_width,
                    )
                st.rerun()
    else:
        st.sidebar.warning("☝️ Please upload a banner creative first!")

# --- DISPLAY OUTPUTS ---

# Output View 1: Standard Static Mockup & Overlay Jobs
if st.session_state.tagged_image_bytes:
    st.header("✅ Results")
    col1, col2 = st.columns(2)

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

    if st.session_state.zip_bytes:
        st.download_button(
            label="📦 Download Both as .zip",
            data=st.session_state.zip_bytes,
            file_name=st.session_state.get('zip_filename', 'package.zip'),
            mime="application/zip",
            use_container_width=True
        )

# Output View 2: Swipe Up Animation & Video Sequence
elif st.session_state.video_bytes or st.session_state.sequence_screens:
    if st.session_state.video_bytes:
        st.header("🎥 Smooth Animation Video Preview")
        vcol1, vcol2 = st.columns([1, 2])
        with vcol1:
            st.video(st.session_state.video_bytes)
            st.download_button(
                label="⬇️ Download Smooth Video (.mp4)",
                data=st.session_state.video_bytes,
                file_name=st.session_state.video_filename,
                mime="video/mp4",
                use_container_width=True,
            )

        st.divider()

    if st.session_state.sequence_screens:
        st.header("🖼️ Individual Frames")
        cols = st.columns(4)

        for i, (label, (img_bytes, filename)) in enumerate(st.session_state.sequence_screens.items()):
            with cols[i % 4]:
                st.subheader(f"#{i+1}")
                st.download_button(
                    label=f"⬇️ Download {label}",
                    data=img_bytes,
                    file_name=filename,
                    mime="image/jpeg",
                    use_container_width=True,
                    key=f"dl_seq_{i}",
                )
                st.image(img_bytes, use_container_width=True)

        st.divider()
        if st.session_state.zip_bytes:
            st.download_button(
                label="📦 Download All (Video + 8 Screens .zip)",
                data=st.session_state.zip_bytes,
                file_name=st.session_state.zip_filename,
                mime="application/zip",
                use_container_width=True,
            )
else:
    st.info("👋 Welcome! Please use the controls in the sidebar to get started.")
