from PIL import Image, ImageDraw
import os

# 创建图标
size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 背景圆
draw.ellipse([10, 10, size-10, size-10], fill=(76, 175, 80, 255))

# 播放按钮三角形
center = size // 2
triangle_size = 60
points = [
    (center - triangle_size//2, center - triangle_size),
    (center - triangle_size//2, center + triangle_size),
    (center + triangle_size//2, center)
]
draw.polygon(points, fill=(255, 255, 255, 255))

# 保存为 ICO
img.save('icon.ico', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print("图标已创建")
