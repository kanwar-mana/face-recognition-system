## 1. Start the face recognition service

cd module3-face-recognition
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

## 2. In a new terminal, run the tests

pytest tests/public/test_face_recognition.py -v
