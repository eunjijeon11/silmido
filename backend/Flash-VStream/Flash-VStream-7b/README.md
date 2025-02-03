---
license: llama2
tags:
- vision-language model
- llama
- video understanding
---

# Flash-VStream Model Card
<a href='https://invinciblewyq.github.io/vstream-page/'><img src='https://img.shields.io/badge/Project-Page-Green'></a> 
<a href='https://arxiv.org/abs/2406.08085v1'><img src='https://img.shields.io/badge/Paper-Arxiv-red'></a>

## Model details
We proposed Flash-VStream, a video-language model that simulates the memory mechanism of human. Our model is able to process extremely long video streams in real-time and respond to user queries simultaneously.

## Training data
This model is trained based on image data from LLaVA-1.5 dataset, and video data from WebVid and ActivityNet datasets following LLaMA-VID, including
- 558K filtered image-text pairs from LAION/CC/SBU, captioned by BLIP.
- 158K GPT-generated multimodal instruction-following data.
- 450K academic-task-oriented VQA data mixture.
- 40K ShareGPT data.
- 232K video-caption pairs sampled from the WebVid 2.5M dataset.
- 98K videos from ActivityNet with QA pairs from Video-ChatGPT.

## License

This project is licensed under the [LLAMA 2 License](LICENSE).
