import subprocess
import cv2
import numpy as np
import threading
import time

# RTMP 스트림 URL
rtmp_url = 'rtmp://10.5.11.57:1935/live/stream'

# 프레임 버퍼 설정
frame_buffer = []
buffer_size = 10  # 버퍼 크기 설정
frame_width, frame_height = 480, 360  # 입력과 출력 프레임 크기 설정

# FFmpeg 명령어 설정 (스트림을 프레임으로 읽기)
ffmpeg_command = [
    'ffmpeg',
    '-listen', '1',  # 서버 역할을 하여 스트림을 수신
    '-i', rtmp_url,
    '-vf', f'scale={frame_width}:{frame_height}',  # 입력 해상도를 360x480으로 설정
    '-f', 'image2pipe',
    '-pix_fmt', 'bgr24',
    '-vcodec', 'rawvideo',
    '-fflags', 'nobuffer',  # 버퍼링 최소화
    '-analyzeduration', '0',  # 분석 시간 최소화
    '-probesize', '32',  # 프로브 크기 최소화
    '-'
]

# FFmpeg 프로세스를 시작하여 스트림 수신
process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)

def read_frame_from_buffer():
    """버퍼에서 1초에 한 프레임씩 읽어와 화면에 표시하는 함수"""
    while True:
        if frame_buffer:
            frame = frame_buffer.pop(0)  # 버퍼에서 첫 번째 프레임을 가져옴
            cv2.imshow('Stream Frame', frame)  # 프레임을 화면에 표시
            if cv2.waitKey(1000) & 0xFF == ord('q'):  # 1초 대기 후 다음 프레임
                break
        else:
            time.sleep(0.1)  # 버퍼가 비어 있으면 잠시 대기

# 프레임을 버퍼에 추가하는 스레드
def buffer_frames():
    """FFmpeg에서 프레임을 읽어와 360x480 크기로 버퍼에 저장하는 함수"""
    while True:
        # 한 프레임의 크기 계산 (360x480 해상도, 3색 채널)
        frame_size = frame_width * frame_height * 3

        # FFmpeg로부터 프레임 데이터를 읽어옴
        frame_data = process.stdout.read(frame_size)
        if len(frame_data) != frame_size:
            print("스트림 종료 또는 프레임 손상")
            break

        # NumPy 배열로 변환하여 OpenCV 프레임 형식으로 변환
        frame = np.frombuffer(frame_data, np.uint8).reshape((frame_height, frame_width, 3))

        # 프레임을 버퍼에 추가
        if len(frame_buffer) < buffer_size:
            frame_buffer.append(frame)
        else:
            print("버퍼가 가득 찼습니다. 오래된 프레임을 삭제하고 새 프레임을 추가합니다.")
            frame_buffer.pop(0)  # 가장 오래된 프레임을 삭제
            frame_buffer.append(frame)

# 프레임을 버퍼에 추가하는 스레드 시작
buffer_thread = threading.Thread(target=buffer_frames)
buffer_thread.daemon = True
buffer_thread.start()

# 버퍼에서 1초에 한 프레임씩 읽어오는 함수 실행
try:
    read_frame_from_buffer()
except KeyboardInterrupt:
    print("스트리밍 중지 중...")
finally:
    process.terminate()
    cv2.destroyAllWindows()
    print("스트리밍 종료 및 창 닫기 완료")
