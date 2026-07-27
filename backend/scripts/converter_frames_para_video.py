import cv2
import glob
import os
from pathlib import Path

def converter_frames_para_video():

    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

    data_dir = PROJECT_ROOT / "data"

    input_folder = data_dir / "m2cai16" / "m2cai16-tool-locations" / "m2cai16-tool-locations" / "JPEGImages"
    output_video_path = data_dir / "m2cai16" / "m2cai16_slideshow.mp4"
    
    # Duração de cada frame esparso em segundos (ex: 1.5s por imagem)
    frame_duration_sec = 1.5
    fps = 25  # FPS padrão de vídeo
    frames_per_image = int(fps * frame_duration_sec)  # 37 quadros repetidos por imagem
    print(input_folder)
    images = sorted(glob.glob(os.path.join(input_folder, "*.jpg")))
    if not images:
        images = sorted(glob.glob(os.path.join(input_folder, "*.png")))
        
    if not images:
        print("Nenhum frame encontrado!")
        return

    # Lê a amostra para pegar resolução
    sample = cv2.imread(images[0])
    h, w, _ = sample.shape
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))

    print(f"Gerando vídeo com {len(images)} frames esparsos (cada um dura {frame_duration_sec}s)...")
    
    # Processa até 30 imagens para gerar um vídeo de ~45 segundos
    for img_path in images[:30]:
        img = cv2.imread(img_path)
        if img is None:
            continue
        # Duplica o frame para criar a sensação de tempo contínuo
        for _ in range(frames_per_image):
            video.write(img)

    video.release()
    print(f"Vídeo gerado em: {output_video_path}")

if __name__ == "__main__":
    converter_frames_para_video()