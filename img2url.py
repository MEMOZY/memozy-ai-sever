import os
import base64

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# 인코딩 할 이미지 경로
image_path = "./005.jpg"

# 이미지 인코딩 수행
encoded_image = encode_image(image_path)

# 인코딩된 이미지 결과를 URL 형식으로 저장
encoded_url = f"data:image/jpeg;base64,{encoded_image}"

# URL을 url.txt 파일에 저장
output_text_path = "./url3.txt"
with open(output_text_path, "w", encoding="utf-8") as text_file:
    text_file.write(encoded_url)

print(f"Image URL saved to {output_text_path}")
