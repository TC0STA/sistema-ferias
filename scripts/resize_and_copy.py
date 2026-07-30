from PIL import Image
import os

src = os.path.join("Imagens", "WhatsApp Image 2026-07-21 at 09.40.41.jpeg")
dst_dir = "uploads"
dst = os.path.join(dst_dir, "fokus.png")

os.makedirs(dst_dir, exist_ok=True)

try:
    img = Image.open(src)
except FileNotFoundError:
    print("Arquivo de origem não encontrado:", src)
    raise

# redimensionar largura para 140px mantendo proporção
new_w = 140
w_percent = (new_w / float(img.width))
new_h = int((float(img.height) * float(w_percent)))
img = img.resize((new_w, new_h), Image.LANCZOS)

img.save(dst, format="PNG")
print("Imagem salva em:", dst)
