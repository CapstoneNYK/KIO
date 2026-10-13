import { useCallback, useEffect, useRef, useState } from "react";

const SILENCE_THRESHOLD = 0.02;
const SILENCE_DURATION_MS = 2200;
const INITIAL_WAIT_MS = 5000;
const MAX_RECORDING_MS = 15000;

interface SttResponse {
  text: string;
}

export const useServerSTT = (language: string = "ko") => {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const spokeRef = useRef(false);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanupAudioGraph = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
    if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
    maxTimerRef.current = null;
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
    }
    audioContextRef.current = null;
    analyserRef.current = null;
  }, []);

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const sendForTranscription = useCallback(
    async (blob: Blob) => {
      setProcessing(true);
      try {
        const formData = new FormData();
        formData.append("file", blob, "speech.webm");
        formData.append("language", language);
        const res = await fetch("/api/stt", { method: "POST", body: formData });
        if (!res.ok) throw new Error(`STT 서버 오류: ${res.status}`);
        const data: SttResponse = await res.json();
        setTranscript(data.text ?? "");
      } catch (error) {
        console.error("STT 요청 실패:", error);
        setTranscript("");
      } finally {
        setProcessing(false);
      }
    },
    [language]
  );

  const stopListening = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }, []);

  const monitorSilence = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.fftSize);

    const tick = () => {
      if (!analyserRef.current) return;
      analyser.getByteTimeDomainData(data);

      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const normalized = (data[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);

      if (rms > SILENCE_THRESHOLD) {
        spokeRef.current = true;
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      } else if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(
          stopListening,
          spokeRef.current ? SILENCE_DURATION_MS : INITIAL_WAIT_MS
        );
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }, [stopListening]);

  const startListening = useCallback(async () => {
    if (listening) return;
    spokeRef.current = false;
    setTranscript("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      mimeTypeRef.current = mimeType;

      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        cleanupAudioGraph();
        releaseStream();
        setListening(false);
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        chunksRef.current = [];
        if (blob.size > 0) {
          sendForTranscription(blob);
        }
      };

      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;

      recorder.start();
      setListening(true);
      monitorSilence();

      maxTimerRef.current = setTimeout(stopListening, MAX_RECORDING_MS);
    } catch (error) {
      console.error("마이크 접근 실패:", error);
      setListening(false);
    }
  }, [listening, monitorSilence, stopListening, cleanupAudioGraph, releaseStream, sendForTranscription]);

  const resetTranscript = useCallback(() => {
    setTranscript("");
  }, []);

  useEffect(() => {
    return () => {
      cleanupAudioGraph();
      releaseStream();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    transcript,
    listening,
    processing,
    startListening,
    stopListening,
    resetTranscript,
  };
};
