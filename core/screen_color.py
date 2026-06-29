import colorsys

from PIL import ImageGrab


def clamp(value, low, high):
    return max(low, min(high, value))


def color_distance(a, b):
    if a is None or b is None:
        return 999
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def hue_distance(a, b):
    if a is None or b is None:
        return 359
    return abs((int(a) - int(b) + 180) % 360 - 180)


def parse_sample_grid(value):
    try:
        width_text, height_text = str(value).lower().replace(" ", "").split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError):
        return 64, 36
    return max(8, min(width, 256)), max(5, min(height, 144))


def screen_size():
    image = ImageGrab.grab()
    size = image.size
    image.close()
    return size


def capture_rect(mode_index, region_percent):
    width, height = screen_size()
    if int(mode_index) == 0:
        return 0, 0, width, height

    scale = clamp(int(region_percent) / 100.0, 0.05, 1.0)
    rect_w = max(10, int(width * scale))
    rect_h = max(10, int(height * scale))
    return int((width - rect_w) / 2), int((height - rect_h) / 2), rect_w, rect_h


def average_screen_color(config, last_color):
    x, y, width, height = capture_rect(config["CaptureModeIndex"], config["RegionPercent"])
    sample_width, sample_height = parse_sample_grid(config.get("SampleGrid", "64 x 36"))
    image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
    image = image.resize((sample_width, sample_height)).convert("RGB")
    pixel_source = getattr(image, "get_flattened_data", image.getdata)
    pixels = list(pixel_source())
    image.close()

    count = len(pixels)
    r = sum(pixel[0] for pixel in pixels) / count
    g = sum(pixel[1] for pixel in pixels) / count
    b = sum(pixel[2] for pixel in pixels) / count

    hue_float, saturation_float, _value_float = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue = int(round(hue_float * 359))
    source_saturation = int(round(saturation_float * 100))
    saturation = source_saturation

    luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    is_dark = luminance < 4
    brightness = int(round((luminance / 255.0) * int(config["BrightnessCap"])))
    brightness = int(clamp(brightness, 1, 100))

    is_neutral = source_saturation < 8
    if is_neutral:
        saturation = 0
    else:
        saturation_boost = 1.0 + (int(config["SaturationBoost"]) / 100.0)
        saturation = int(clamp(round(saturation * saturation_boost), 1, 100))

    if not is_dark and saturation >= 25:
        brightness = max(brightness, 8)

    smoothing = int(config["SmoothingPercent"])
    if last_color is not None and smoothing > 0:
        alpha = clamp(smoothing / 100.0, 0.0, 0.95)
        if not is_neutral and last_color["saturation"] > 0:
            previous_hue = last_color["hue"]
            hue_delta = ((hue - previous_hue + 180) % 360) - 180
            hue = int(round((previous_hue + hue_delta * (1.0 - alpha)) % 360))
        saturation = int(round(last_color["saturation"] * alpha + saturation * (1.0 - alpha)))
        brightness = int(round(last_color["brightness"] * alpha + brightness * (1.0 - alpha)))
        if is_neutral:
            saturation = 0

    hue = int(clamp(hue, 1, 359))
    saturation = int(clamp(saturation, 0, 100))
    brightness = int(clamp(brightness, 1, 100))
    if saturation <= 3:
        gray = int(clamp(round((brightness / 100.0) * 255), 0, 255))
        rgb = (gray, gray, gray)
        hue = 1
        saturation = 0
    else:
        display_rgb = colorsys.hsv_to_rgb(hue / 359.0, saturation / 100.0, brightness / 100.0)
        rgb = tuple(int(clamp(round(channel * 255), 0, 255)) for channel in display_rgb)

    return {
        "rgb": rgb,
        "hue": hue,
        "saturation": saturation,
        "brightness": brightness,
        "is_dark": is_dark,
        "is_neutral": saturation <= 3,
    }
