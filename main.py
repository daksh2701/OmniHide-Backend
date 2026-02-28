from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import cv2
import numpy as np
import wave
from cryptography.fernet import Fernet

app = FastAPI(title="OmniHide Stego API", description="Image, Audio, and Video Steganography Suite")

# CORS Setup (Frontend connection ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp", exist_ok=True)

# Master Key
MASTER_KEY = b'tuS3XSjmDuX5D-6h1MMQODe-PJMsO7FYPfO6O60NNl0='
cipher_suite = Fernet(MASTER_KEY)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# ==========================================
# 1. IMAGE LOGIC (Super Fast Version)
# ==========================================
def encode_image_logic(image_path, secret_message, output_path):
    image = cv2.imread(image_path)
    secret_message += "#####"
    binary_secret_msg = ''.join([format(ord(i), "08b") for i in secret_message])
    flat_image = image.flatten()
    for i in range(len(binary_secret_msg)):
        flat_image[i] = (flat_image[i] & 254) | int(binary_secret_msg[i])
    encoded_image = flat_image.reshape(image.shape)
    cv2.imwrite(output_path, encoded_image)

@app.post("/encode/image/")
async def api_encode_image(secret_text: str = Form(...), file: UploadFile = File(...)):
    input_path = f"temp/{file.filename}"
    output_filename = f"stego_{file.filename.split('.')[0]}.png"
    output_path = f"temp/{output_filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    encrypted_text = cipher_suite.encrypt(secret_text.encode()).decode()
    encode_image_logic(input_path, encrypted_text, output_path)
    return FileResponse(output_path, media_type="image/png", filename=output_filename)

# ==========================================
# 2. AUDIO LOGIC (.wav files)
# ==========================================
def encode_audio_logic(audio_path, secret_message, output_path):
    song = wave.open(audio_path, mode='rb')
    frame_bytes = bytearray(list(song.readframes(song.getnframes())))
    secret_message += "#####"
    binary_msg = ''.join([format(ord(i), "08b") for i in secret_message])
    for i in range(len(binary_msg)):
        frame_bytes[i] = (frame_bytes[i] & 254) | int(binary_msg[i])
    with wave.open(output_path, 'wb') as fd:
        fd.setparams(song.getparams())
        fd.writeframes(bytes(frame_bytes))
    song.close()

@app.post("/encode/audio/")
async def api_encode_audio(secret_text: str = Form(...), file: UploadFile = File(...)):
    input_path = f"temp/{file.filename}"
    output_filename = f"stego_{file.filename.split('.')[0]}.wav"
    output_path = f"temp/{output_filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    encrypted_text = cipher_suite.encrypt(secret_text.encode()).decode()
    encode_audio_logic(input_path, encrypted_text, output_path)
    return FileResponse(output_path, media_type="audio/wav", filename=output_filename)

# ==========================================
# 3. VIDEO LOGIC (.avi files)
# ==========================================
def encode_video_logic(video_path, secret_message, output_path):
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    out = cv2.VideoWriter(output_path, 0, fps, (width, height)) # 0 means Uncompressed
    secret_message += "#####"
    binary_msg = ''.join([format(ord(i), "08b") for i in secret_message])
    frame_number = 0
    data_hidden = False
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        if frame_number == 0 and not data_hidden:
            flat_frame = frame.flatten()
            for i in range(len(binary_msg)):
                flat_frame[i] = (flat_frame[i] & 254) | int(binary_msg[i])
            frame = flat_frame.reshape(frame.shape)
            data_hidden = True
        out.write(frame)
        frame_number += 1
    cap.release()
    out.release()

@app.post("/encode/video/")
async def api_encode_video(secret_text: str = Form(...), file: UploadFile = File(...)):
    input_path = f"temp/{file.filename}"
    output_filename = f"stego_{file.filename.split('.')[0]}.avi"
    output_path = f"temp/{output_filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    encrypted_text = cipher_suite.encrypt(secret_text.encode()).decode()
    encode_video_logic(input_path, encrypted_text, output_path)
    return FileResponse(output_path, media_type="video/avi", filename=output_filename)


# ==========================================
# 4. ULTIMATE DECODE LOGIC (All Media Types)
# ==========================================

@app.post("/decode/image/")
async def api_decode_image(file: UploadFile = File(...)):
    input_path = f"temp/decode_{file.filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Super-fast Numpy Decode
    image = cv2.imread(input_path)
    flat_image = image.flatten()
    lsb_array = flat_image & 1
    packed_bytes = np.packbits(lsb_array)
    extracted_data = packed_bytes.tobytes().decode('utf-8', errors='ignore')
    
    delimiter_index = extracted_data.find("#####")
    if delimiter_index != -1:
        extracted_gibberish = extracted_data[:delimiter_index]
        try:
            decrypted_text = cipher_suite.decrypt(extracted_gibberish.encode()).decode()
            return {"status": "success", "secret_message": decrypted_text}
        except Exception:
            return {"status": "error", "message": "Decryption failed! Lock change ho gaya ya data corrupt hai."}
            
    return {"status": "error", "message": "Image mein koi hidden data nahi mila."}

@app.post("/decode/audio/")
async def api_decode_audio(file: UploadFile = File(...)):
    input_path = f"temp/decode_{file.filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    song = wave.open(input_path, mode='rb')
    frame_bytes = bytearray(list(song.readframes(song.getnframes())))
    
    extracted = ""
    for byte in frame_bytes:
        extracted += str(byte & 1)
        
    all_bytes = [extracted[i: i+8] for i in range(0, len(extracted), 8)]
    decoded_data = ""
    for byte in all_bytes:
        decoded_data += chr(int(byte, 2))
        if decoded_data[-5:] == "#####":
            break
            
    if decoded_data[-5:] == "#####":
        extracted_gibberish = decoded_data[:-5]
        try:
            decrypted_text = cipher_suite.decrypt(extracted_gibberish.encode()).decode()
            return {"status": "success", "secret_message": decrypted_text}
        except Exception:
            return {"status": "error", "message": "Decryption failed!"}
            
    return {"status": "error", "message": "Audio mein koi hidden data nahi mila."}

@app.post("/decode/video/")
async def api_decode_video(file: UploadFile = File(...)):
    input_path = f"temp/decode_{file.filename}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    cap = cv2.VideoCapture(input_path)
    ret, frame = cap.read() # Humne sirf pehle frame mein data dala tha
    cap.release()
    
    if not ret: 
        return {"status": "error", "message": "Video read nahi ho payi."}
        
    flat_frame = frame.flatten()
    lsb_array = flat_frame & 1
    packed_bytes = np.packbits(lsb_array)
    extracted_data = packed_bytes.tobytes().decode('utf-8', errors='ignore')
    
    delimiter_index = extracted_data.find("#####")
    if delimiter_index != -1:
        extracted_gibberish = extracted_data[:delimiter_index]
        try:
            decrypted_text = cipher_suite.decrypt(extracted_gibberish.encode()).decode()
            return {"status": "success", "secret_message": decrypted_text}
        except Exception:
            return {"status": "error", "message": "Decryption failed!"}
            
    return {"status": "error", "message": "Video mein koi hidden data nahi mila."}