"""
위암 진단 AI 서비스 - Multi-Task Learning (MTL) 버전
Segmentation + Classification 동시 수행
모델 파일이 없어도 서버가 정상 시작되도록 graceful 처리

v3: predict_batch() 메서드 추가 (동적 배칭 지원)
"""

import logging
from pathlib import Path
from typing import Dict, Union, List
import time

logger = logging.getLogger(__name__)

# PyTorch 관련 import (선택적 의존성)
try:
    import torch
    import torch.nn as nn
    from torchvision import transforms
    from PIL import Image
    import numpy as np
    import io
    import base64
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed. AI features will be disabled.")

# smp 관련 import (선택적 의존성)
try:
    import segmentation_models_pytorch as smp
    SMP_AVAILABLE = True
except ImportError:
    SMP_AVAILABLE = False
    logger.warning("segmentation_models_pytorch not installed. AI features will be disabled.")

from app.core.config import settings


class GastricMTLModel(nn.Module if TORCH_AVAILABLE else object):
    def __init__(self, n_seg_classes=5, n_cls_classes=4):
        if not TORCH_AVAILABLE or not SMP_AVAILABLE:
            return
        super().__init__()
        self.unet = smp.Unet(
            encoder_name="resnet50",
            encoder_weights="imagenet",
            in_channels=3,
            classes=n_seg_classes
        )
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Sequential(
            nn.Linear(2048, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(512, n_cls_classes)
        )

    def forward(self, x):
        features = self.unet.encoder(x)
        decoder_output = self.unet.decoder(features)
        seg_out = self.unet.segmentation_head(decoder_output)
        cls_feat = self.avgpool(features[-1])
        cls_feat = torch.flatten(cls_feat, 1)
        cls_out = self.classifier(cls_feat)
        return seg_out, cls_out

    def freeze_encoder(self):
        for param in self.unet.encoder.parameters():
            param.requires_grad = False

    def unfreeze_all(self):
        for param in self.parameters():
            param.requires_grad = True


class MTLAIService:
    """AI 진단 서비스 (MTL) - 모델 없어도 서버 시작 가능"""
    
    CLASS_NAMES = ["STDI", "STNT", "STIN", "STMX"]
    CLASS_NAMES_KR = ["미만형선암", "위염", "장형선암", "혼합형선암"]
    SEG_CLASS_NAMES = ["Background", "Tumor", "Stroma", "Normal", "Immune"]
    SEG_CLASS_NAMES_KR = ["배경", "종양", "기질", "정상", "면역세포"]
    SEG_COLORS = {
        0: [0, 0, 0],       # Background - 검정
        1: [255, 0, 0],     # Tumor - 빨강
        2: [0, 255, 0],     # Stroma - 초록
        3: [0, 0, 255],     # Normal - 파랑
        4: [255, 255, 0],   # Immune - 노랑
    }
    
    def __init__(self, model_path: str = None):
        self.model_path = Path(model_path or settings.AI_MODEL_PATH)
        self.model = None
        self.transform = None
        
        if not TORCH_AVAILABLE or not SMP_AVAILABLE:
            logger.warning("AI dependencies not available. AI service running in mock mode.")
            return
            
        self.device = torch.device(settings.AI_DEVICE if torch.cuda.is_available() else "cpu")
        self.transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        self._load_model()
    
    def _load_model(self):
        if not self.model_path.exists():
            logger.warning(f"Model file not found: {self.model_path}. AI prediction will use mock data.")
            print(f"AI Model file not found: {self.model_path}")
            print("  AI prediction will use mock/demo data until model file is provided.")
            return
        
        try:
            self.model = GastricMTLModel(n_seg_classes=5, n_cls_classes=4)
            state_dict = torch.load(self.model_path, map_location=self.device, weights_only=False)
            missing_keys, unexpected_keys = self.model.load_state_dict(state_dict, strict=False)
            if missing_keys:
                logger.warning(f"Missing keys: {len(missing_keys)}")
            if unexpected_keys:
                logger.warning(f"Unexpected keys: {len(unexpected_keys)}")
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"MTL Model loaded: {self.model_path}, Device: {self.device}")
            print(f"AI Model loaded successfully: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load MTL model: {e}")
            print(f"Failed to load AI model: {e}")
            self.model = None
    
    def predict(self, image_input: Union[str, bytes]) -> Dict:
        """이미지 예측 - 모델이 없으면 mock 데이터 반환"""
        start_time = time.time()
        
        if self.model is None or not TORCH_AVAILABLE:
            return self._mock_predict(start_time)
        
        try:
            if isinstance(image_input, str):
                image = Image.open(image_input).convert('RGB')
            else:
                image = Image.open(io.BytesIO(image_input)).convert('RGB')
            original_size = image.size
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                features = self.model.unet.encoder(input_tensor)
                decoder_output = self.model.unet.decoder(*features)
                seg_out = self.model.unet.segmentation_head(decoder_output)
                cls_feat = self.model.avgpool(features[-1])
                cls_feat = torch.flatten(cls_feat, 1)
                cls_out = self.model.classifier(cls_feat)
                
            cls_probs = torch.softmax(cls_out, dim=1)[0]
            cls_pred = torch.argmax(cls_probs).item()
            confidence = cls_probs[cls_pred].item()
            seg_pred = torch.argmax(seg_out, dim=1)[0].cpu().numpy()
            seg_stats = self._calculate_segmentation_stats(seg_pred)
            
            # 3가지 이미지 생성: 원본(리사이즈), 오버레이, 세그 마스크
            original_b64 = self._image_to_base64(image.resize((512, 512)))
            overlay_b64 = self._create_segmentation_overlay(image, seg_pred)
            mask_b64 = self._create_segmentation_mask(seg_pred)
            
            processing_time = time.time() - start_time
            
            return {
                "prediction": self.CLASS_NAMES[cls_pred],
                "prediction_kr": self.CLASS_NAMES_KR[cls_pred],
                "confidence": float(confidence),
                "probabilities": {name: float(prob) for name, prob in zip(self.CLASS_NAMES, cls_probs.cpu().numpy())},
                "probabilities_kr": {name: float(prob) for name, prob in zip(self.CLASS_NAMES_KR, cls_probs.cpu().numpy())},
                "raw_logits": cls_out[0].cpu().numpy().tolist(),
                "segmentation": {
                    "stats": seg_stats,
                    "original_base64": original_b64,
                    "overlay_base64": overlay_b64,
                    "mask_base64": mask_b64,
                    "class_colors": self.SEG_COLORS,
                    "class_names_kr": dict(zip(
                        [name.lower() for name in self.SEG_CLASS_NAMES],
                        self.SEG_CLASS_NAMES_KR
                    ))
                },
                "processing_time": processing_time,
                "model_info": {
                    "model_type": "UNet + ResNet50 (MTL)",
                    "input_size": [512, 512],
                    "original_size": list(original_size),
                    "device": str(self.device),
                }
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"error": True, "message": str(e)}

    def predict_batch(self, image_bytes_list: List[bytes]) -> List[Dict]:
        """
        배치 추론 - 여러 이미지를 한번에 처리
        동적 배칭 엔진에서 호출됨
        
        Args:
            image_bytes_list: 이미지 바이트 리스트
            
        Returns:
            각 이미지에 대한 예측 결과 딕셔너리 리스트
        """
        if self.model is None or not TORCH_AVAILABLE:
            # Mock 모드: 각 이미지에 대해 mock 결과 반환
            return [self._mock_predict(time.time()) for _ in image_bytes_list]

        batch_start = time.time()
        results = []

        try:
            # 1. 이미지 전처리 및 텐서 배치 구성
            images = []
            tensors = []
            original_sizes = []

            for img_bytes in image_bytes_list:
                image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                images.append(image)
                original_sizes.append(image.size)
                tensors.append(self.transform(image))

            # (N, C, H, W) 배치 텐서
            batch_tensor = torch.stack(tensors).to(self.device)

            # 2. 배치 추론
            with torch.no_grad():
                features = self.model.unet.encoder(batch_tensor)
                decoder_output = self.model.unet.decoder(*features)
                seg_out = self.model.unet.segmentation_head(decoder_output)
                cls_feat = self.model.avgpool(features[-1])
                cls_feat = torch.flatten(cls_feat, 1)
                cls_out = self.model.classifier(cls_feat)

            # 3. 배치 결과를 개별 결과로 분리
            cls_probs_batch = torch.softmax(cls_out, dim=1)
            seg_preds_batch = torch.argmax(seg_out, dim=1).cpu().numpy()

            batch_elapsed = time.time() - batch_start

            for i in range(len(image_bytes_list)):
                item_start = time.time()
                cls_probs = cls_probs_batch[i]
                cls_pred = torch.argmax(cls_probs).item()
                confidence = cls_probs[cls_pred].item()
                seg_pred = seg_preds_batch[i]
                seg_stats = self._calculate_segmentation_stats(seg_pred)

                original_b64 = self._image_to_base64(images[i].resize((512, 512)))
                overlay_b64 = self._create_segmentation_overlay(images[i], seg_pred)
                mask_b64 = self._create_segmentation_mask(seg_pred)

                # 개별 처리 시간 = 배치 총 시간 / 배치 크기 (공평 배분)
                per_item_time = batch_elapsed / len(image_bytes_list)

                results.append({
                    "prediction": self.CLASS_NAMES[cls_pred],
                    "prediction_kr": self.CLASS_NAMES_KR[cls_pred],
                    "confidence": float(confidence),
                    "probabilities": {
                        name: float(prob)
                        for name, prob in zip(self.CLASS_NAMES, cls_probs.cpu().numpy())
                    },
                    "probabilities_kr": {
                        name: float(prob)
                        for name, prob in zip(self.CLASS_NAMES_KR, cls_probs.cpu().numpy())
                    },
                    "raw_logits": cls_out[i].cpu().numpy().tolist(),
                    "segmentation": {
                        "stats": seg_stats,
                        "original_base64": original_b64,
                        "overlay_base64": overlay_b64,
                        "mask_base64": mask_b64,
                        "class_colors": self.SEG_COLORS,
                        "class_names_kr": dict(zip(
                            [name.lower() for name in self.SEG_CLASS_NAMES],
                            self.SEG_CLASS_NAMES_KR
                        ))
                    },
                    "processing_time": per_item_time,
                    "model_info": {
                        "model_type": "UNet + ResNet50 (MTL)",
                        "input_size": [512, 512],
                        "original_size": list(original_sizes[i]),
                        "device": str(self.device),
                        "batch_size": len(image_bytes_list),
                    }
                })

            logger.info(
                f"Batch prediction completed: {len(image_bytes_list)} items "
                f"in {batch_elapsed:.3f}s"
            )
            return results

        except Exception as e:
            logger.error(f"Batch prediction error: {e}")
            # 실패 시 개별 추론으로 폴백
            logger.info("Falling back to individual prediction")
            return [self.predict(img_bytes) for img_bytes in image_bytes_list]
    
    def _mock_predict(self, start_time: float) -> Dict:
        """모델이 없을 때 데모/목업 데이터 반환"""
        processing_time = time.time() - start_time
        return {
            "prediction": "STIN",
            "prediction_kr": "장형선암",
            "confidence": 0.8734,
            "probabilities": {"STDI": 0.0521, "STNT": 0.0613, "STIN": 0.8734, "STMX": 0.0132},
            "probabilities_kr": {"미만형선암": 0.0521, "위염": 0.0613, "장형선암": 0.8734, "혼합형선암": 0.0132},
            "raw_logits": [1.2, 1.6, 3.5, 0.9],
            "segmentation": {
                "stats": {
                    "ratios": {"background": 0.001, "tumor": 0.325, "stroma": 0.288, "normal": 0.254, "immune": 0.132},
                    "pixel_counts": {"background": 262, "tumor": 85197, "stroma": 75497, "normal": 66585, "immune": 34603}
                },
                "original_base64": "",
                "overlay_base64": "",
                "mask_base64": "",
                "class_colors": self.SEG_COLORS,
                "class_names_kr": {
                    "background": "배경", "tumor": "종양", "stroma": "기질",
                    "normal": "정상", "immune": "면역세포"
                }
            },
            "processing_time": processing_time,
            "model_info": {
                "model_type": "UNet + ResNet50 (MTL) [DEMO MODE]",
                "input_size": [512, 512],
                "original_size": [512, 512],
                "device": "cpu",
            }
        }
    
    def _calculate_segmentation_stats(self, seg_mask) -> Dict:
        total_pixels = seg_mask.size
        stats = {"ratios": {}, "pixel_counts": {}}
        for cls_id, cls_name in enumerate(self.SEG_CLASS_NAMES):
            count = int(np.sum(seg_mask == cls_id))
            ratio = count / total_pixels
            stats["ratios"][cls_name.lower()] = float(ratio)
            stats["pixel_counts"][cls_name.lower()] = count
        return stats
    
    def _image_to_base64(self, pil_image) -> str:
        """PIL 이미지를 base64 문자열로 변환"""
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    
    def _create_segmentation_overlay(self, original_image, seg_mask) -> str:
        """원본 이미지 위에 세그멘테이션 결과를 반투명 오버레이"""
        img_resized = original_image.resize((512, 512))
        img_np = np.array(img_resized)
        color_mask = np.zeros((512, 512, 3), dtype=np.uint8)
        for cls_id, color in self.SEG_COLORS.items():
            color_mask[seg_mask == cls_id] = color
        alpha = 0.45
        overlay = (img_np * (1 - alpha) + color_mask * alpha).astype(np.uint8)
        overlay_img = Image.fromarray(overlay)
        return self._image_to_base64(overlay_img)
    
    def _create_segmentation_mask(self, seg_mask) -> str:
        """세그멘테이션 마스크 이미지 (색상만, 원본 없이)"""
        color_mask = np.zeros((512, 512, 3), dtype=np.uint8)
        for cls_id, color in self.SEG_COLORS.items():
            color_mask[seg_mask == cls_id] = color
        mask_img = Image.fromarray(color_mask)
        return self._image_to_base64(mask_img)
    
    def get_model_info(self) -> Dict:
        return {
            "model_path": str(self.model_path),
            "device": str(getattr(self, 'device', 'N/A')),
            "model_loaded": self.model is not None,
            "model_type": "UNet + ResNet50 (MTL)",
            "num_seg_classes": 5,
            "num_cls_classes": 4,
            "classification_classes": self.CLASS_NAMES_KR,
            "segmentation_classes": self.SEG_CLASS_NAMES_KR,
        }


# 싱글톤 인스턴스 (서버 시작 시 안전하게 초기화)
# FastAPI 서버에서는 모델을 로드하지 않음 (Celery 워커에서만 로드)
# 하지만 get_model_info() 등 메타데이터 조회용으로 인스턴스는 생성
try:
    ai_service = MTLAIService()
    logger.info("MTL AI Service initialized")
except Exception as e:
    logger.error(f"Failed to initialize MTL AI Service: {e}")
    print(f"AI Service initialization failed: {e}")
    ai_service = MTLAIService.__new__(MTLAIService)
    ai_service.model = None
    ai_service.model_path = Path(settings.AI_MODEL_PATH)
    ai_service.transform = None
