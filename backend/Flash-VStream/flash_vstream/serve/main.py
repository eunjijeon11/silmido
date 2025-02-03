from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging

import argparse
import requests
import logging
import torch
import numpy as np
import time
import os
import cv2

from flash_vstream.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from flash_vstream.conversation import conv_templates, SeparatorStyle
from flash_vstream.model.builder import load_pretrained_model
from flash_vstream.utils import disable_torch_init
from flash_vstream.mm_utils import process_images, tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria

from torch.multiprocessing import Process, Queue, Manager
from transformers import TextStreamer
from decord import VideoReader
from datetime import datetime
from PIL import Image
from io import BytesIO

# parameters
model_path = "/home/reagankoo/VQA/Flash-VStream/Flash-VStream-7b"
device = "cuda"
conv_mode = "vicuna_v1"
temperature = 0.0
max_new_tokens = 512
video_max_frames = 1200
video_fps = 1.0

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 허용할 클라이언트 출처를 명시
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)


class Question(BaseModel):
    question: str

class _Metric:
    def __init__(self):
        self._latest_value = None
        self._sum = 0.0
        self._max = 0.0
        self._count = 0

    @property
    def val(self):
        return self._latest_value

    @property
    def max(self):
        return self._max

    @property
    def avg(self):
        if self._count == 0:
            return float('nan')
        return self._sum / self._count

    def add(self, value):
        self._latest_value = value
        self._sum += value
        self._count += 1
        if value > self._max:
            self._max = value

    def __str__(self):
        latest_formatted = f"{self.val:.6f}" if self.val is not None else "None"
        average_formatted = f"{self.avg:.6f}"
        max_formatted = f"{self.max:.6f}"
        return f"{latest_formatted} ({average_formatted}, {max_formatted})"        

class MetricMeter:
    def __init__(self):
        self._metrics = {}

    def add(self, key, value):
        if key not in self._metrics:
            self._metrics[key] = _Metric()
        self._metrics[key].add(value)

    def val(self, key):
        metric = self._metrics.get(key)
        if metric is None or metric.val is None:
            raise ValueError(f"No values have been added for key '{key}'.")
        return metric.val

    def avg(self, key):
        metric = self._metrics.get(key)
        if metric is None:
            raise ValueError(f"No values have been added for key '{key}'.")
        return metric.avg

    def max(self, key):
        metric = self._metrics.get(key)
        if metric is None:
            raise ValueError(f"No values have been added for key '{key}'.")
        return metric.max

    def __getitem__(self, key):
        metric = self._metrics.get(key)
        if metric is None:
            raise KeyError(f"The key '{key}' does not exist.")
        return str(metric)

########## init ###########
#torch.multiprocessing.set_start_method('spawn', force=True)
disable_torch_init()

frame_queue = Queue(maxsize=10)
p3 = None

model_name = get_model_name_from_path(model_path)
tokenizer = None
model = None
image_processor = None 
context_len = None

conv = conv_templates[conv_mode].copy()
if "mpt" in model_name.lower():
	roles = ('user', 'assistant')
else:
	roles = conv.roles
     
start_time = None
time_meter = None
conv_cnt = None

image_tensor = None

logging.basicConfig(
    level=logging.INFO,  # 로그 레벨 설정
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 로그 메시지 형식
)

logger = logging.getLogger(__name__)

manager = None

def frame_memory_manager(model, image_processor, frame_queue):
    ############## Start sub process-3: Memory Manager #############
    time_meter = MetricMeter()
    logger.info(f"manager start")
    frame_cnt = 0
    
    while True:
        try:
            video_clip = frame_queue.get()
            start_time = time.perf_counter()
            if video_clip is None:
                break
            # logger.info(f"read clip")
            image = image_processor.preprocess(video_clip, return_tensors='pt')['pixel_values']
            image = image.unsqueeze(0)
            image_tensor = image.to(model.device, dtype=torch.float16)
            # time_2 = time.perf_counter()
            with torch.inference_mode():
                model.embed_video_streaming(image_tensor)
            end_time = time.perf_counter()
            if frame_cnt > 0:
                time_meter.add('memory_latency', end_time - start_time)
            frame_cnt += video_clip.shape[0]
        except Exception as e:
            print(f'MemManager Exception: {e}')
            time.sleep(0.1)

@app.get("/ready")
def ready():
    global tokenizer, model, image_processor, context_len
    if model is None:
        tokenizer, model, image_processor, context_len = load_pretrained_model(model_path, None, model_name, False, False, device=device)
    
    global manager
    manager = Manager()
    
    model.use_video_streaming_mode = True
    model.video_embedding_memory = manager.list()
    model.config.video_max_frames = video_max_frames
    
    global p3
    p3 = Process(target=frame_memory_manager, args=(model, image_processor, frame_queue))
    p3.start()
				
    global start_time
    start_time = datetime.now()
    global time_meter
    time_meter = MetricMeter()
    global conv_cnt
    conv_cnt = 0
    
    return {"message":"server ready"}

@app.post("/send_video")
async def send_video(frame: UploadFile = File(...)):
    contents = await frame.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    img = img.reshape(-1,360,480,3)
    #logger.info(img)
    frame_queue.put(img)
    return None

@app.post("/send_question")
def send_question(question: Question):
	inp = question.question
	global logger
	logger.info("Root endpoint was called")
	if not inp:
		return {"answer": "send proper message"}
	#conv_start_time = time.perf_counter()

	conv = conv_templates[conv_mode].copy()
	inp = DEFAULT_IMAGE_TOKEN + '\n' + inp
	conv.append_message(conv.roles[0], inp)

	conv.append_message(conv.roles[1], None)
	prompt = conv.get_prompt()

	input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(0).to(model.device)
	stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
	keywords = [stop_str]
	stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)
	streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

	#llm_start_time = time.perf_counter()
	with torch.inference_mode():
		output_ids = model.generate(
			input_ids,
			images=image_tensor,
			do_sample=True if temperature > 0 else False,
			temperature=temperature,
			max_new_tokens=max_new_tokens,
			streamer=streamer,
			use_cache=True,
			stopping_criteria=[stopping_criteria]
		)
	llm_end_time = time.perf_counter()

	outputs = tokenizer.decode(output_ids[0, input_ids.shape[1]:]).strip()
	conv.messages[-1][-1] = outputs
	#conv_end_time = time.perf_counter()
    
	# if conv_cnt > 0:
	# 	time_meter.add('conv_latency', conv_end_time - conv_start_time)
	# 	time_meter.add('llm_latency', llm_end_time - llm_start_time)
	# 	time_meter.add('real_sleep', conv_start_time - last_conv_start_time)
	global conv_cnt
	conv_cnt += 1
	#last_conv_start_time = conv_start_time
	return {"answer": outputs}

@app.get("/bye")
def bye():
    p3.terminate()
    print("All processes finished.")
    return {"message": "server bye"}

if __name__ == '__main__':
    app.run(host = "127.0.0.1", port=8080)