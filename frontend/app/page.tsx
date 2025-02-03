"use client";

import { useState, useEffect, useRef, FormEvent } from 'react';
import OpenAI from "openai";

// const openai = new OpenAI({
//   apiKey: 'YOUR_API_KEY',
//   dangerouslyAllowBrowser: true // WARNING: Do NOT expose your API key in production
// });

export default function Home() {
  const imgRef = useRef<HTMLImageElement>(null);
  const [text, setText] = useState('');
  const [apiResponse, setApiResponse] = useState<string | null>(null);
  const [shouldSendFrame, setShouldSendFrame] = useState(false);
  const [isImageLoaded, setIsImageLoaded] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const sendReadyCalled = useRef(false);

  // Function to send 'ready' signal when the website renders
  // Ref to track if sendReady has been called


  // Function to send 'ready' signal when the website renders
  const sendReady = async () => {
    console.log('Sending ready signal');
    try {
      await fetch('http://localhost:8080/ready', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      console.log('Ready signal sent');
    } catch (error) {
      console.error('Error sending ready signal:', error);
    }
  };

  // Function to send 'bye' signal when the button is clicked
  const sendBye = async () => {
    try {
      await fetch('http://localhost:8080/bye', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      console.log('Bye signal sent');
    } catch (error) {
      console.error('Error sending bye signal:', error);
    }
  };

  const handleImageError = () => {
    console.log('Image failed to load');
    setIsImageLoaded(false);
  };

  const handleImageLoad = () => {
    console.log('Image loaded');
    setIsImageLoaded(true);
  };

  const captureAndSendFrame = () => {
    if (!imgRef.current || !isImageLoaded) return;

    const img = imgRef.current;

    if (!img.complete || img.naturalWidth === 0 || img.naturalHeight === 0) {
      console.log('Image not loaded properly, skipping frame capture.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    const context = canvas.getContext('2d');
    if (context) {
      context.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(async (blob) => {
        if (blob) {
          const formData = new FormData();
          formData.append('frame', blob, 'frame.jpg');

          try {
            const response = await fetch('http://localhost:8080/send_video', {
              method: 'POST',
              body: formData,
            });
            const result = await response.json();
            console.log('Frame sent:', result);
          } catch (error) {
            console.error('Frame send error:', error);
          }
        }
      }, 'image/jpeg');
    }
  };

  useEffect(() => {
    if (imgRef.current) {
      imgRef.current.crossOrigin = 'anonymous';
      imgRef.current.src = 'http://localhost:8001/video_feed';
    }

    let intervalId: NodeJS.Timeout | null = null;

    if (isImageLoaded) {
      intervalId = setInterval(() => {
        setShouldSendFrame(true);
      }, 1000);
    } else {
      console.log('Image not loaded, stopping frame capture');
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isImageLoaded]);

  useEffect(() => {
    if (shouldSendFrame && isImageLoaded) {
      captureAndSendFrame();
      setShouldSendFrame(false);
    }
  }, [shouldSendFrame, isImageLoaded]);

  useEffect(() => {
    if (!sendReadyCalled.current) {
      sendReady();
      sendReadyCalled.current = true;
    }
  }, []);

  // Function to start audio recording
  const startRecording = () => {
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = handleAudioStop;
      mediaRecorder.start();
      setIsRecording(true);
    });
  };

  // Function to stop audio recording
  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  // Handle audio recording stop and send to server for transcription
  const handleAudioStop = async () => {
    const audioBlob = new Blob(audioChunksRef.current, { type: "audio/mp3" });
    audioChunksRef.current = [];

    const transcription = await transcribeAudio(audioBlob);
    if (transcription) {
      console.log('Transcription:', transcription);
      setText(transcription);
      handleTextSubmission(transcription);
    }
  };

  // Function to transcribe audio using OpenAI Whisper
  const transcribeAudio = async (audioBlob: Blob) => {
    const file = new File([audioBlob], "audio.mp3", { type: "audio/mp3" });
    try {
      const transcription = await openai.audio.transcriptions.create({
        file,
        model: "whisper-1",
      });
      return transcription.text;
    } catch (error) {
      console.error("Audio transcription error:", error);
      return null;
    }
  };

  // Function to handle text submission and get response
  const handleTextSubmission = async (text: string) => {
    try {
      const response = await fetch('http://localhost:8080/send_question', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: text }),
      });
      const result = await response.json();
      setApiResponse(result.answer);

      await speakResponse(result.answer);
    } catch (error) {
      console.error("Text submission error:", error);
    }
  };

  // Function to convert text response to speech
  const speakResponse = async (text: string) => {
    try {
      const speech = await openai.audio.speech.create({
        model: "tts-1",
        voice: "alloy",
        input: text,
      });
      const audioBuffer = Buffer.from(await speech.arrayBuffer());
      const audioBlob = new Blob([audioBuffer], { type: "audio/mp3" });
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.play();
    } catch (error) {
      console.error("Speech synthesis error:", error);
    }
  };

  return (
    <div className="container">
      <h1>See:Quence</h1>
      <img
        ref={imgRef}
        alt="RTMP Stream"
        style={{ width: '640px', height: '480px' }}
        onError={handleImageError}
        onLoad={handleImageLoad}
      />
      <form onSubmit={(e) => { e.preventDefault(); handleTextSubmission(text); }} className="text-form">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter your question"
        />
        <button type="submit">Send</button>
      </form>
      <button onClick={isRecording ? stopRecording : startRecording}>
        {isRecording ? "Stop Recording" : "Start Recording"}
      </button>
      <button onClick={sendBye}>Send Bye</button>
      {apiResponse && <p className="api-response">Response: {apiResponse}</p>}
    </div>
  );
}
