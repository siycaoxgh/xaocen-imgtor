"""Small pure helpers used by tests after the legacy Tk cropper is archived."""


def canvas_rect_to_image(start_x, start_y, end_x, end_y,
                         image_x, image_y, scale, image_width, image_height):
    """Convert canvas coordinates to a clamped source-image rectangle."""
    x1 = int((min(start_x, end_x) - image_x) / scale)
    y1 = int((min(start_y, end_y) - image_y) / scale)
    x2 = int((max(start_x, end_x) - image_x) / scale)
    y2 = int((max(start_y, end_y) - image_y) / scale)
    return (
        max(0, min(image_width, x1)),
        max(0, min(image_height, y1)),
        max(0, min(image_width, x2)),
        max(0, min(image_height, y2)),
    )
