from PIL import Image, ImageDraw, ImageFont
import os

def create_professional_icon():
    # High resolution for quality
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw gradient circle
    for i in range(size//2):
        alpha = 255
        # Purple gradient from center to edge
        r = int(99 + (i/size*2) * 30)
        g = int(102 + (i/size*2) * 20)
        b = int(241 - (i/size*2) * 20)
        
        offset = i
        draw.ellipse(
            [offset, offset, size-offset, size-offset],
            fill=(r, g, b, alpha)
        )
    
    # Main circle with border
    padding = 20
    draw.ellipse(
        [padding, padding, size-padding, size-padding],
        fill=(99, 102, 241, 255),
        outline=(129, 140, 248, 255),
        width=12
    )
    
    # Inner glow
    inner_padding = 40
    draw.ellipse(
        [inner_padding, inner_padding, size-inner_padding, size-inner_padding],
        fill=(109, 112, 251, 255)
    )
    
    # Draw "VII" text
    try:
        # Try different fonts
        font_paths = [
            "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        font = None
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, 200)
                break
        if not font:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    text = "VII"
    
    # Get text size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 30
    
    # Draw shadow
    shadow_offset = 6
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(30, 30, 60, 150), font=font)
    
    # Draw main text
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    
    # Create electron folder
    os.makedirs('electron', exist_ok=True)
    
    # Save 256x256 PNG
    img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    img_256.save('electron/icon.png', 'PNG')
    print('✅ Created: electron/icon.png')
    
    # Create multi-size ICO
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images = [img.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    ico_images[0].save('electron/icon.ico', format='ICO', sizes=[(s,s) for s in sizes])
    print('✅ Created: electron/icon.ico')
    
    print('\n🎉 Professional VII icon created!')

if __name__ == '__main__':
    create_professional_icon()