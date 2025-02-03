#!/bin/bash

python -m flash_vstream.serve.video_stream \
    --model-path Flash-VStream-7b \
    --video-file assets/example.mp4 \
    --conv-mode vicuna_v1 --temperature 0.0 \
    --video_max_frames 1200 \
    --video_fps 1.0 --play_speed 1.0 \
    --log-file realtime_cli.log
