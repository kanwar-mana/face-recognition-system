# How to Run the Face Recognition Module

## 1. Install dependencies (from project root)

pip install -r module3-face-recognition/requirements.txt

## 2. Download model files (one-time, into module3-face-recognition/)

cd module3-face-recognition
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite" -OutFile "blaze_face_short_range.tflite"
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/image_embedder/mobilenet_v3_small/float32/latest/mobilenet_v3_small.tflite" -OutFile "mobilenet_v3_small.tflite"

## 3. Start the face recognition service

cd module3-face-recognition
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

## 4. In a new terminal, run the tests

pytest tests/public/test_face_recognition.py -v
