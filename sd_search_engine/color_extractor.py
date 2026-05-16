from pathlib import Path
from PIL import Image


COLOR_NAMES = {
    "red": [(255, 0, 0), (200, 0, 0), (139, 0, 0)],
    "green": [(0, 128, 0), (0, 255, 0), (34, 139, 34)],
    "blue": [(0, 0, 255), (0, 0, 139), (65, 105, 225)],
    "yellow": [(255, 255, 0), (204, 204, 0), (128, 128, 0)],
    "purple": [(128, 0, 128), (75, 0, 130), (138, 43, 226)],
    "orange": [(255, 165, 0), (255, 140, 0), (255, 69, 0)],
    "pink": [(255, 192, 203), (255, 105, 180), (219, 112, 147)],
    "brown": [(165, 42, 42), (139, 69, 19), (101, 67, 33)],
    "gray": [(128, 128, 128), (169, 169, 169), (192, 192, 192)],
    "black": [(0, 0, 0), (20, 20, 20), (40, 40, 40)],
    "white": [(255, 255, 255), (240, 240, 240), (220, 220, 220)],
    "cyan": [(0, 255, 255), (0, 206, 209), (64, 224, 208)],
    "magenta": [(255, 0, 255), (199, 21, 133), (186, 85, 211)],
}


def find_closest_color_name(rgb):
    r, g, b = rgb
    min_distance = float("inf")
    closest_color = "gray"
    
    for color_name, color_values in COLOR_NAMES.items():
        for target_rgb in color_values:
            distance = (
                (r - target_rgb[0]) ** 2
                + (g - target_rgb[1]) ** 2
                + (b - target_rgb[2]) ** 2
            ) ** 0.5
            
            if distance < min_distance:
                min_distance = distance
                closest_color = color_name
    
    return closest_color


def rgb_to_hex(rgb):
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def extract_dominant_color(image_path):
    try:
        image = Image.open(image_path)
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Scale down if too big
        max_pixels = 100000
        total_pixels = image.width * image.height
        
        if total_pixels > max_pixels:
            scale = (max_pixels / total_pixels) ** 0.5
            new_width = max(1, int(image.width * scale))
            new_height = max(1, int(image.height * scale))
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Count colors by iterating with two for loops
        color_count = {}
        
        for y in range(image.height):
            for x in range(image.width):
                pixel = image.getpixel((x, y))
                if isinstance(pixel, tuple):
                    rgb = pixel[:3]
                else:
                    rgb = (pixel, pixel, pixel)
                
                rgb = tuple(int(c) for c in rgb)
                color_count[rgb] = color_count.get(rgb, 0) + 1
        
        # Get top 5 colors
        sorted_colors = sorted(color_count.items(), key=lambda item: item[1], reverse=True)
        top_colors = [color for color, count in sorted_colors[:5]]
        
        if not top_colors:
            top_colors = [(128, 128, 128)]
        
        dominant_color = top_colors[0]
        
        # Build color palette
        color_palette = [
            {
                "rgb": color,
                "hex": rgb_to_hex(color),
                "name": find_closest_color_name(color),
            }
            for color in top_colors
        ]
        
        return {
            "dominant_color": dominant_color,
            "dominant_color_name": find_closest_color_name(dominant_color),
            "dominant_color_hex": rgb_to_hex(dominant_color),
            "color_palette": color_palette,
        }
        
    except Exception as e:
        return {
            "dominant_color": (128, 128, 128),
            "dominant_color_name": "gray",
            "dominant_color_hex": "#808080",
            "color_palette": [
                {
                    "rgb": (128, 128, 128),
                    "hex": "#808080",
                    "name": "gray",
                }
            ],
        }

