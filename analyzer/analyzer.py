import cv2 
import os
import time
import random
import pyautogui
from PIL import ImageGrab
from ultralytics import YOLO
import numpy as np
from loguru import logger 


class Analyzer:
    def __init__(self):
        logger.info("Initializing Analyzer")
        self._load_model()

    def _load_model(self):
        logger.info("Loading YOLO model")
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(script_dir, "best.pt")
            if not os.path.exists(model_path):
                logger.error(f"Model file '{model_path}' not found")
                raise FileNotFoundError(f"Model file '{model_path}' not found")
            
            self.model = YOLO(model_path, verbose=False)
            logger.success(f"YOLOv8 model loaded successfully from {model_path}")
            
        except Exception as e:
            logger.error(f"Error loading YOLOv8 model: {e}")
            self.model = None

    def wait_for_page_load(self):
        logger.info("Waiting for page to load (checking for at least 5 elements)")
        for attempt in range(10):
            logger.debug(f"Page load attempt {attempt + 1}/10")
            elements = self.detect_elements()
            
            if elements is None:
                logger.warning(f"Attempt {attempt + 1}: Failed to detect elements")
                continue
                
            element_count = len(elements)
            logger.debug(f"Attempt {attempt + 1}: Found {element_count} elements")
            
            if element_count <= 0:
                logger.info(f"Attempt {attempt + 1}: Didn't find any  elements, need at least 1. Waiting...")
                time.sleep(5)
                continue 
                
            logger.success(f"Page loaded successfully with {element_count} elements detected")
            return True 
            
        logger.error("Page failed to load after 10 attempts")
        return False 
    
    def click_element_by_class(self, class_name, min_elements=1, expected_count=1, max_attempts=3, wait_between_attempts=3.0):
        logger.info(f"Attempting to click {class_name} element (max attempts: {max_attempts})")
        
        for attempt in range(max_attempts):
            if max_attempts > 1:
                logger.debug(f"Attempt {attempt + 1}/{max_attempts} for {class_name}")
            
            elements = self.detect_elements()
            
            if elements is None:
                if attempt == max_attempts - 1:  # Last attempt
                    logger.error("Failed to detect any elements on page")
                    return "Failed to detect elements on page"
                else:
                    logger.warning(f"Attempt {attempt + 1}: Failed to detect elements, retrying in {wait_between_attempts}s")
                    time.sleep(wait_between_attempts)
                    continue
                    
            element_count = len(elements)
            logger.debug(f"Detected {element_count} elements on page")
            
            if element_count < min_elements:
                if attempt == max_attempts - 1:  # Last attempt
                    logger.warning(f"Only found {element_count} elements, expected at least {min_elements}")
                    return f"Not all elements found on page (found {element_count}, expected at least {min_elements})"
                else:
                    logger.debug(f"Attempt {attempt + 1}: Only found {element_count} elements, retrying in {wait_between_attempts}s")
                    time.sleep(wait_between_attempts)
                    continue
                    
            # Log all detected elements for debugging
            element_classes = [element['class_name'] for element in elements]
            logger.debug(f"Detected element classes: {element_classes}")
                
            target_elements = [element for element in elements if element['class_name'] == class_name]
            target_count = len(target_elements)
            
            logger.debug(f"Found {target_count} {class_name} elements")
            
            if target_count != expected_count:
                if attempt == max_attempts - 1:  # Last attempt
                    logger.error(f"Expected {expected_count} {class_name} element(s), found {target_count}")
                    return f"Failed to find {class_name} element on page (found {target_count}, expected {expected_count})"
                else:
                    logger.debug(f"Attempt {attempt + 1}: Found {target_count} {class_name} elements, expected {expected_count}, retrying in {wait_between_attempts}s")
                    time.sleep(wait_between_attempts)
                    continue
            
            # Found the target element(s), proceed with click
            target_element = target_elements[0]
            logger.info(f"Found {class_name} element at center: {target_element['center']} (confidence: {target_element['confidence']:.3f})")
            
            success = self.click_element(target_element)
            if success:
                logger.success(f"Successfully clicked {class_name} element")
                return f"Successfully clicked {class_name}"
            else:
                if attempt == max_attempts - 1:  # Last attempt
                    logger.error(f"Failed to click {class_name} element")
                    return f"Failed to click {class_name}"
                else:
                    logger.warning(f"Attempt {attempt + 1}: Failed to click {class_name}, retrying in {wait_between_attempts}s")
                    time.sleep(wait_between_attempts)
                    continue
        
        # This should never be reached, but just in case
        logger.error(f"All {max_attempts} attempts failed for {class_name}")
        return f"Failed to click {class_name} after {max_attempts} attempts"

    
    def click_element(self, element):
        try:
            center_x, center_y = element['center']
            class_name = element['class_name']
            confidence = element['confidence']

            if class_name == 'USERNAME_INPUT' or class_name == 'PASSWORD_INPUT':
                center_y = center_y + 30
            
            logger.info(f"Clicking {class_name} element (confidence: {confidence:.2f}) at coordinates ({center_x:.1f}, {center_y:.1f})")
            
            pyautogui.click(center_x, center_y)
            logger.success(f"Successfully clicked {class_name} element")
            return True
            
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            return False

    def type_text_human_like(self, text, base_delay=0.08, variation=0.05, typo_chance=0.02, pause_chance=0.05):
        try:
            logger.info(f"Typing text with human-like behavior: '{text}' (length: {len(text)} characters)")
            
            for i, char in enumerate(text):
                # Random delay between keystrokes
                delay = base_delay + random.uniform(-variation, variation)
                delay = max(0.01, delay)  # Ensure minimum delay
                
                # Occasional typos
                if random.random() < typo_chance and char.isalpha():
                    # Type a wrong character first
                    wrong_chars = 'qwertyuiopasdfghjklzxcvbnm'
                    wrong_char = random.choice(wrong_chars)
                    if wrong_char != char.lower():
                        logger.debug(f"Making typo: typing '{wrong_char}' instead of '{char}'")
                        pyautogui.typewrite(wrong_char)
                        time.sleep(random.uniform(0.1, 0.3))  # Pause before correction
                        pyautogui.press('backspace')  # Delete wrong character
                        time.sleep(random.uniform(0.05, 0.15))  # Brief pause after correction
                
                # Type the actual character
                pyautogui.typewrite(char)
                
                # Occasional longer pauses (like thinking/reading)
                if random.random() < pause_chance:
                    pause_duration = random.uniform(0.2, 0.8)
                    logger.debug(f"Taking thinking pause: {pause_duration:.2f}s")
                    time.sleep(pause_duration)
                else:
                    time.sleep(delay)
            
            logger.success(f"Successfully typed text with human-like behavior: '{text}'")
            return True
            
        except Exception as e:
            logger.error(f"Error typing text '{text}': {e}")
            return False
    
    def type_text_random(self, text):
        return self.type_text_human_like(
            text,
            base_delay=random.uniform(0.03, 0.15),     # Random base delay
            variation=random.uniform(0.02, 0.08),      # Random variation
            typo_chance=random.uniform(0.0, 0.05),     # Random typo chance
            pause_chance=random.uniform(0.0, 0.1)      # Random pause chance
        )

    def screenshot(self):
        try:
            logger.debug("Capturing screenshot")
            screenshot = ImageGrab.grab()
            screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            logger.debug(f"Screenshot captured: {screenshot_cv.shape}")
            return screenshot_cv
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    def detect_elements(self):
        logger.debug("Starting element detection")
        screenshot = self.screenshot()
        if screenshot is None:
            logger.error("Failed to capture screenshot for detection")
            return None
        
        results = None 
        try:
            logger.debug("Running YOLO model on screenshot")
            results = self.model(screenshot)
        except Exception as e:
            logger.error(f"Error during object detection: {e}")
            return None

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                logger.warning("No boxes detected in result")
                return []
            
            logger.debug(f"Processing {len(boxes)} detected boxes")
            
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = box.conf[0].cpu().numpy()
                class_id = int(box.cls[0].cpu().numpy())
                class_name = self.model.names[class_id]

                if confidence < 0.5:
                    logger.debug(f"Detection {i+1}: {class_name} (confidence: {confidence:.3f} too low. Skipping)")
                    continue
                
                detection = {
                    "class_name": class_name,
                    "class_id": class_id,
                    "confidence": float(confidence),
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "center": [float((x1 + x2) / 2), float((y1 + y2) / 2)]
                }
                
                logger.debug(f"Detection {i+1}: {class_name} (confidence: {confidence:.3f})")
                detections.append(detection)
        
        logger.info(f"Element detection completed: found {len(detections)} elements")
        return detections