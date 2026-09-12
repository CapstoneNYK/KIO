import { useCallback, useEffect, useRef, useState } from "react";

// 마이크 RMS 볼륨이 이 값 이하면 "침묵"으로 간주한다. 마이크/환경마다 감도가
// 다르므로 실제 기기에서 테스트해보며 값을 조정해야 한다.
const SILENCE_THRESHOLD = 0.02;
// 침묵이 이 시간(ms) 이상 지속되면 자동으로 녹음을 끊고 서버로 전송한다.
const SILENCE_DURATION_MS = 1200;
// 안전장치: 아무리 말이 길어도 이 시간이 지나면 강제로 녹음을 종료한다.
const MAX_RECORDING_MS = 15000;

interface SttResponse {
  text: string;
}

/**
 * 브라우저 내장 Web Speech API(react-speech-recognition) 대신,
 * 자체 서버(FastAPI + faster-whisper)에서 음성을 텍스트로 변환하는 STT 훅.
 *
 * 교수님 피드백: 카페처럼 배경 소음이 있는 환경에서 Web Speech API 오인식이
 * 잦다는 지적이 있었다. 이 훅은
 *   1) getUserMedia에 noiseSuppression/echoCancellation/autoGainControl을 적용하고
 *   2) 볼륨 기반 VAD로 침묵을 감지해 발화가 끝나면 자동으로 녹음을 끊고
 *   3) 녹음된 오디오를 서버의 Whisper 모델(VAD 필터 포함)로 보내 인식 결과를 받는다.
 *
 * 기존 useSTT와 동일한 인터페이스(transcript/listening/startListening/
 * stopListening/resetTranscript)를 반환하므로 SpeechInput 쪽 로직은 그대로
 * 재사용할 수 있다. 다만 인식 결과가 "녹음 종료 후" 한 번에 도착하기 때문에
 * 녹음 중 실시간 자막(interim transcript)은 제공하지 않는다.
 */
export const useServerSTT = (language: string = "ko") => {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  // 녹음은 이미 끝났고 서버에 보내서 인식 결과를 기다리는 중인지 여부.
  // listening과 분리해두지 않으면, 정지 버튼을 눌러도 서버 응답이 올 때까지
  // (특히 STT 모델을 medium 등으로 바꿔서 느려졌을 때) 화면이 계속 "듣는 중"
  // 상태로 보여서 마치 정지가 안 되는 것처럼 느껴지는 문제가 있었다.
  const [processing, setProcessing] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string>("audio/webm");
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
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

  // 녹음 중이면 정지(-> onstop에서 서버 전송), 이미 정지/전송 대기 중이면 아무 것도 하지 않는다.
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
      if (!analyserRef.current) return; // 이미 정리된 경우 중단
      analyser.getByteTimeDomainData(data);

      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const normalized = (data[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);

      if (rms > SILENCE_THRESHOLD) {
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      } else if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(stopListening, SILENCE_DURATION_MS);
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }, [stopListening]);

  const startListening = useCallback(async () => {
    if (listening) return;
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
        // 녹음 자체는 여기서 이미 끝났으므로, 서버 응답을 기다리기 전에
        // listening을 바로 꺼서 "정지" 동작이 즉시 반영되도록 한다.
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

  // 언마운트 시 마이크/오디오 컨텍스트 정리
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
