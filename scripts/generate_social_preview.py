"""
Pulse — 1280x640 Social Card Generator.
Generates the official GitHub Social Preview asset for MrTG1B/Pulse.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_social_preview():
    width = 1280
    height = 640

    # Base background #0A0A0A
    img = Image.new("RGBA", (width, height), (10, 10, 10, 255))

    # Fonts
    font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    font_title = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 76)
    font_tagline = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 36)
    font_sub = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 24)
    font_badge = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 14)
    font_code = ImageFont.truetype(os.path.join(font_dir, "consolab.ttf"), 15)
    font_widget_title = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 18)
    font_widget_big = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 42)
    font_widget_sm = ImageFont.truetype(os.path.join(font_dir, "segoeui.ttf"), 14)
    font_widget_bold_sm = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 14)

    # Ambient background lime glow around widget
    glow_lime = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_lime)
    glow_draw.ellipse([(650, 40), (1350, 620)], fill=(184, 255, 61, 22))
    glow_lime = glow_lime.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img, glow_lime)
    draw = ImageDraw.Draw(img)

    # Very subtle, elegant grid dots or faint lines
    for x in range(0, width, 80):
        for y in range(0, height, 80):
            draw.point((x, y), fill=(50, 50, 50, 160))

    # Clean outer subtle border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(32, 32, 32, 255), width=2)

    # Left content column
    x_left = 90
    y_logo = 110

    # Load and place Pulse icon
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((108, 108), Image.Resampling.LANCZOS)
        
        # Rounded mask for icon
        mask = Image.new("L", (108, 108), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (108, 108)], radius=24, fill=255)
        
        # Icon glow
        icon_shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        is_draw = ImageDraw.Draw(icon_shadow)
        is_draw.rounded_rectangle([(x_left - 6, y_logo - 6), (x_left + 114, y_logo + 114)], radius=28, fill=(184, 255, 61, 55))
        icon_shadow = icon_shadow.filter(ImageFilter.GaussianBlur(16))
        img = Image.alpha_composite(img, icon_shadow)
        draw = ImageDraw.Draw(img)

        img.paste(icon, (x_left, y_logo), mask)

    # Main Brand Header: "PULSE"
    y_title = y_logo + 135
    draw.text((x_left, y_title), "PULSE", font=font_title, fill=(255, 255, 255, 255))

    # Tagline: "Know when your models are ready."
    y_tagline = y_title + 88
    draw.text((x_left, y_tagline), "Know when your models are ready.", font=font_tagline, fill=(184, 255, 61, 255))

    # Targeted product association
    y_sub = y_tagline + 56
    draw.text((x_left, y_sub), "AgentRouter  \u2022  Claude Code  \u2022  Codex", font=font_sub, fill=(160, 160, 160, 255))

    # Feature badges / pills
    y_pills = y_sub + 56
    pills = ["402 Quota Detection", "Local Reset Countdown", "Live Model Discovery"]
    curr_x = x_left
    for p in pills:
        bbox = font_badge.getbbox(p)
        p_w = (bbox[2] - bbox[0]) + 26
        draw.rounded_rectangle([(curr_x, y_pills), (curr_x + p_w, y_pills + 32)], radius=8, fill=(18, 18, 18, 255), outline=(42, 42, 42, 255), width=1)
        draw.text((curr_x + 13, y_pills + 7), p, font=font_badge, fill=(200, 200, 200, 255))
        curr_x += p_w + 10

    # RIGHT COLUMN: Floating Widget Preview
    w_x = 730
    w_y = 65
    w_w = 460
    w_h = 510

    # Widget shadow
    w_shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ws_draw = ImageDraw.Draw(w_shadow)
    ws_draw.rounded_rectangle([(w_x - 12, w_y - 12), (w_x + w_w + 12, w_y + w_h + 12)], radius=26, fill=(0, 0, 0, 200))
    ws_draw.rounded_rectangle([(w_x, w_y), (w_x + w_w, w_y + w_h)], radius=20, fill=(184, 255, 61, 30))
    w_shadow = w_shadow.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, w_shadow)
    draw = ImageDraw.Draw(img)

    # Widget Container
    draw.rounded_rectangle([(w_x, w_y), (w_x + w_w, w_y + w_h)], radius=20, fill=(17, 17, 17, 255), outline=(44, 44, 44, 255), width=2)

    # Top Widget Titlebar
    draw.line([(w_x, w_y + 54), (w_x + w_w, w_y + 54)], fill=(32, 32, 32, 255), width=1)
    draw.ellipse([(w_x + 22, w_y + 21), (w_x + 34, w_y + 33)], fill=(255, 77, 77, 255))
    draw.ellipse([(w_x + 42, w_y + 21), (w_x + 54, w_y + 33)], fill=(255, 184, 77, 255))
    draw.ellipse([(w_x + 62, w_y + 21), (w_x + 74, w_y + 33)], fill=(184, 255, 61, 255))
    draw.text((w_x + 95, w_y + 17), "Pulse \u2014 AgentRouter Monitor", font=font_widget_title, fill=(245, 245, 245, 255))

    # Connection Status Banner
    cy = w_y + 72
    draw.rounded_rectangle([(w_x + 20, cy), (w_x + w_w - 20, cy + 46)], radius=10, fill=(14, 22, 10, 255), outline=(184, 255, 61, 120), width=1)
    draw.ellipse([(w_x + 36, cy + 17), (w_x + 48, cy + 29)], fill=(184, 255, 61, 255))
    draw.text((w_x + 58, cy + 14), "Gateway Online", font=font_widget_bold_sm, fill=(184, 255, 61, 255))
    draw.text((w_x + 180, cy + 14), "\u2022  agentrouter.org  (142ms)", font=font_widget_sm, fill=(160, 160, 160, 255))

    # Quota Window Countdown Hero Box
    qy = cy + 62
    draw.rounded_rectangle([(w_x + 20, qy), (w_x + w_w - 20, qy + 148)], radius=12, fill=(11, 11, 11, 255), outline=(36, 36, 36, 255), width=1)
    draw.text((w_x + 36, qy + 16), "NEXT QUOTA REPLENISHMENT WINDOW", font=font_badge, fill=(138, 138, 138, 255))
    draw.text((w_x + 36, qy + 42), "16:30 IST", font=font_widget_big, fill=(184, 255, 61, 255))
    draw.text((w_x + 245, qy + 54), "(in 38m 12s)", font=font_widget_title, fill=(255, 184, 77, 255))
    draw.text((w_x + 36, qy + 110), "\u25cf Detected 402 Budget Pool Exhaustion", font=font_widget_sm, fill=(255, 120, 120, 255))

    # Active Models List
    my = qy + 166
    draw.text((w_x + 22, my), "ACTIVE MODELS", font=font_badge, fill=(138, 138, 138, 255))
    my += 26

    models = [
        ("claude-opus-4-8", "READY", (184, 255, 61)),
        ("claude-opus-5", "READY", (184, 255, 61)),
        ("gpt-6-astra", "READY", (184, 255, 61)),
        ("deepseek-v4-flash", "ACTIVE", (184, 255, 61)),
    ]

    for name, st, col in models:
        draw.rounded_rectangle([(w_x + 20, my), (w_x + w_w - 20, my + 30)], radius=6, fill=(13, 13, 13, 255), outline=(28, 28, 28, 255), width=1)
        draw.ellipse([(w_x + 32, my + 11), (w_x + 40, my + 19)], fill=col)
        draw.text((w_x + 50, my + 6), name, font=font_code, fill=(230, 230, 230, 255))
        draw.text((w_x + w_w - 85, my + 7), st, font=font_badge, fill=col)
        my += 36

    # Save social preview
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    output_path = os.path.join(output_dir, "social_preview.png")
    img.save(output_path, "PNG", quality=95)
    print(f"Social preview created successfully at {output_path} ({width}x{height})")

if __name__ == "__main__":
    create_social_preview()
