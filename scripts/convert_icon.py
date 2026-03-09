#!/usr/bin/env python3
"""Generate a simple app icon for Strava registration."""

from PIL import Image, ImageDraw

def create_app_icon(size=(512, 512)):
    """Create a simple GetTracks app icon."""
    # Create image with Strava orange background
    img = Image.new('RGBA', size, (252, 76, 2, 255))  # #FC4C02
    draw = ImageDraw.Draw(img)

    # Draw a white track/path shape
    # Simple curved path representation
    points = [(100, 200), (256, 150), (412, 200), (412, 312), (256, 362), (100, 312)]
    draw.polygon(points, fill=(255, 255, 255, 255))

    # Add start and end circles
    draw.ellipse([80, 180, 120, 220], fill=(255, 255, 255, 255))  # Start
    draw.ellipse([392, 180, 432, 220], fill=(252, 76, 2, 255))    # End (orange)

    # Add a simple arrow
    arrow_points = [(320, 180), (350, 200), (320, 220)]
    draw.polygon(arrow_points, fill=(252, 76, 2, 255))

    return img

if __name__ == "__main__":
    icon = create_app_icon()
    icon.save("app_icon.png", "PNG")
    print("App icon generated: app_icon.png")
    print("Size: 512x512 pixels")
    print("Upload this PNG file to your Strava app registration.")