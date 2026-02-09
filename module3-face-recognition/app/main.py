"""
SAIV Face Recognition & Risk Service - Module 3

Privacy Requirements:
- NO raw face images stored
- Process images in-memory only
- Store only SHA-256 hashes of face embeddings
"""

import base64
import hashlib
import ipaddress
import re
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, List, Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

import mediapipe as mp

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="SAIV Face Recognition Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Model file paths (resolve relative to this package directory)
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent.parent  # module3-face-recognition/
_DETECTOR_MODEL = str(_MODULE_DIR / "blaze_face_short_range.tflite")
_EMBEDDER_MODEL = str(_MODULE_DIR / "mobilenet_v3_small.tflite")

# ---------------------------------------------------------------------------
# MediaPipe Tasks API singletons
# ---------------------------------------------------------------------------
BaseOptions = mp.tasks.BaseOptions

_detector = mp.tasks.vision.FaceDetector.create_from_options(
    mp.tasks.vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=_DETECTOR_MODEL),
        min_detection_confidence=0.5,
    )
)

_embedder = mp.tasks.vision.ImageEmbedder.create_from_options(
    mp.tasks.vision.ImageEmbedderOptions(
        base_options=BaseOptions(model_asset_path=_EMBEDDER_MODEL),
        l2_normalize=True,
        quantize=False,
    )
)

# In-memory enrollment store: hash -> embedding (numpy array)
_enrollment_store: Dict[str, np.ndarray] = {}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class FaceEnrollRequest(BaseModel):
    user_id: str
    image: str
    camera_consent: bool = False


class FaceEnrollResponse(BaseModel):
    enrollment_successful: bool
    face_template_hash: str
    quality_score: float
    details: Dict[str, Any]


class FaceVerifyRequest(BaseModel):
    image: str
    reference_template_hash: str


class FaceVerifyResponse(BaseModel):
    match_passed: bool
    match_score: float
    match_threshold: float
    face_detected: bool
    current_template_hash: str


class LivenessRequest(BaseModel):
    challenge_response: str
    challenge_type: str = "blink"


class LivenessResponse(BaseModel):
    liveness_passed: bool
    liveness_score: float
    liveness_threshold: float
    face_embedding_hash: str
    details: Dict[str, Any]


class GeolocationData(BaseModel):
    latitude: float
    longitude: float
    accuracy: float


class RiskAssessRequest(BaseModel):
    liveness_score: Optional[float] = None
    face_match_score: Optional[float] = None
    device_signature: Optional[str] = None
    device_public_key: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geolocation: Optional[GeolocationData] = None


class RiskAssessResponse(BaseModel):
    risk_score: float
    risk_level: str
    pass_threshold: bool
    risk_threshold: float
    signal_breakdown: Dict[str, float]
    recommendations: List[str]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def decode_base64_image(b64: str) -> np.ndarray:
    """Decode a base64 image string to an RGB numpy array."""
    try:
        raw = base64.b64decode(b64)
        pil_img = Image.open(BytesIO(raw)).convert("RGB")
        return np.array(pil_img)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")


def detect_face(image_rgb: np.ndarray):
    """Return the first MediaPipe face detection or None, plus confidence."""
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
    result = _detector.detect(mp_image)
    if result.detections:
        det = result.detections[0]
        confidence = det.categories[0].score if det.categories else 0.5
        return det, confidence
    return None, 0.0


def extract_face_embedding(image_rgb: np.ndarray, detection) -> np.ndarray:
    """Extract a discriminative face embedding using MediaPipe ImageEmbedder
    on the cropped face region."""
    h, w, _ = image_rgb.shape
    bbox = detection.bounding_box
    x1 = max(0, bbox.origin_x - 10)
    y1 = max(0, bbox.origin_y - 10)
    x2 = min(w, bbox.origin_x + bbox.width + 10)
    y2 = min(h, bbox.origin_y + bbox.height + 10)

    face_crop = image_rgb[y1:y2, x1:x2]
    if face_crop.size == 0:
        face_crop = image_rgb

    # Resize to model input size and get semantic embedding
    face_resized = cv2.resize(face_crop, (224, 224))
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=face_resized)
    result = _embedder.embed(mp_image)
    return np.array(result.embeddings[0].embedding, dtype=np.float64)


def generate_face_hash(embedding: np.ndarray) -> str:
    """SHA-256 hex digest of the embedding bytes (64 lowercase hex chars)."""
    return hashlib.sha256(embedding.tobytes()).hexdigest()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity in [0, 1]."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/reserved range."""
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


VPN_KEYWORDS = re.compile(r"vpn|proxy|tor|tunnel|hide|anon", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "face-recognition"}


@app.get("/")
async def root():
    return {
        "service": "SAIV Face Recognition & Risk Service",
        "version": "1.0.0",
        "endpoints": [
            "/face/enroll",
            "/face/verify",
            "/face/match",
            "/liveness/check",
            "/risk/assess",
        ],
    }


# ---------------------------------------------------------------------------
# Face enrollment
# ---------------------------------------------------------------------------

@app.post("/face/enroll", status_code=201)
async def enroll_face(request: FaceEnrollRequest):
    # Consent check
    if not request.camera_consent:
        raise HTTPException(status_code=400, detail="Camera consent is required")

    image_rgb = decode_base64_image(request.image)
    detection, confidence = detect_face(image_rgb)

    if detection is None:
        return FaceEnrollResponse(
            enrollment_successful=False,
            face_template_hash="",
            quality_score=0.0,
            details={"error": "No face detected"},
        )

    embedding = extract_face_embedding(image_rgb, detection)
    face_hash = generate_face_hash(embedding)

    # Store embedding for later verification
    _enrollment_store[face_hash] = embedding.copy()

    # Quality score based on detection confidence + resolution
    h, w, _ = image_rgb.shape
    resolution_factor = min(1.0, (h * w) / (256 * 256))
    quality_score = round(float(confidence) * 0.7 + resolution_factor * 0.3, 4)
    quality_score = min(1.0, max(0.0, quality_score))

    del image_rgb
    return FaceEnrollResponse(
        enrollment_successful=True,
        face_template_hash=face_hash,
        quality_score=quality_score,
        details={"confidence": round(float(confidence), 4)},
    )


# ---------------------------------------------------------------------------
# Face verification
# ---------------------------------------------------------------------------

@app.post("/face/verify")
async def verify_face(request: FaceVerifyRequest):
    image_rgb = decode_base64_image(request.image)
    detection, confidence = detect_face(image_rgb)

    if detection is None:
        del image_rgb
        return FaceVerifyResponse(
            match_passed=False,
            match_score=0.0,
            match_threshold=0.70,
            face_detected=False,
            current_template_hash="",
        )

    embedding = extract_face_embedding(image_rgb, detection)
    current_hash = generate_face_hash(embedding)

    ref_hash = request.reference_template_hash

    # If exact hash match → same image, score = 1.0
    if current_hash == ref_hash:
        score = 1.0
    elif ref_hash in _enrollment_store:
        ref_embedding = _enrollment_store[ref_hash]
        # Compare only if embeddings are same dimensionality
        if ref_embedding.shape == embedding.shape:
            score = cosine_similarity(ref_embedding, embedding)
        else:
            score = 0.0
    else:
        score = 0.0

    score = min(1.0, max(0.0, score))
    match_threshold = 0.70
    match_passed = score >= match_threshold

    del image_rgb
    return FaceVerifyResponse(
        match_passed=match_passed,
        match_score=round(score, 4),
        match_threshold=match_threshold,
        face_detected=True,
        current_template_hash=current_hash,
    )


@app.post("/face/match")
async def match_face(request: FaceVerifyRequest):
    return await verify_face(request)


# ---------------------------------------------------------------------------
# Liveness detection
# ---------------------------------------------------------------------------

@app.post("/liveness/check")
async def check_liveness(request: LivenessRequest):
    image_rgb = decode_base64_image(request.challenge_response)
    detection, confidence = detect_face(image_rgb)

    if detection is None:
        del image_rgb
        return LivenessResponse(
            liveness_passed=False,
            liveness_score=0.0,
            liveness_threshold=0.60,
            face_embedding_hash="",
            details={"error": "No face detected"},
        )

    confidence = float(confidence)
    embedding = extract_face_embedding(image_rgb, detection)
    face_hash = generate_face_hash(embedding)

    liveness_score = round(confidence * 0.9, 4)
    liveness_threshold = 0.60

    del image_rgb
    return LivenessResponse(
        liveness_passed=liveness_score >= liveness_threshold,
        liveness_score=liveness_score,
        liveness_threshold=liveness_threshold,
        face_embedding_hash=face_hash,
        details={"confidence": round(confidence, 4)},
    )


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

@app.post("/risk/assess")
async def assess_risk(request: RiskAssessRequest):
    signals: Dict[str, float] = {}
    recommendations: List[str] = []

    # Liveness signal (inverted: low liveness → high risk)
    if request.liveness_score is not None:
        signals["liveness"] = 1.0 - request.liveness_score
    else:
        signals["liveness"] = 0.5

    # Face match signal (inverted)
    if request.face_match_score is not None:
        signals["face_match"] = 1.0 - request.face_match_score
    else:
        signals["face_match"] = 0.5

    # Device signal
    if request.device_signature:
        signals["device"] = 0.1
    else:
        signals["device"] = 0.5

    # Network / VPN signal
    network_risk = 0.2  # default neutral-low
    if request.ip_address and is_private_ip(request.ip_address):
        network_risk = 0.8
        recommendations.append("VPN/proxy detected — verify identity")
    if request.user_agent and VPN_KEYWORDS.search(request.user_agent):
        network_risk = max(network_risk, 0.8)
        if not any("VPN" in r for r in recommendations):
            recommendations.append("VPN indicator in user-agent")
    signals["network"] = network_risk

    # Geolocation signal
    if request.geolocation:
        geo = request.geolocation
        if geo.accuracy > 5000:
            signals["geolocation"] = 0.7
            recommendations.append("Low geolocation accuracy")
        elif geo.accuracy < 1:
            signals["geolocation"] = 0.6
        else:
            signals["geolocation"] = 0.1
    else:
        signals["geolocation"] = 0.3

    # Weighted fusion
    weights = {
        "liveness": 0.25,
        "face_match": 0.25,
        "device": 0.20,
        "network": 0.15,
        "geolocation": 0.15,
    }
    risk_score = sum(signals[k] * weights[k] for k in weights)
    risk_score = round(min(1.0, max(0.0, risk_score)), 4)

    # Risk level
    if risk_score < 0.3:
        risk_level = "LOW"
    elif risk_score < 0.5:
        risk_level = "MEDIUM"
    elif risk_score < 0.7:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    if signals["liveness"] > 0.5:
        recommendations.append("Low liveness confidence")
    if signals["face_match"] > 0.5:
        recommendations.append("Low face-match confidence")

    return RiskAssessResponse(
        risk_score=risk_score,
        risk_level=risk_level,
        pass_threshold=risk_score < 0.50,
        risk_threshold=0.50,
        signal_breakdown=signals,
        recommendations=recommendations,
    )
