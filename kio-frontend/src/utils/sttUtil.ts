import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";
import { useRef, useEffect } from "react";

export const useSTT = (language: string = "ko-KR") => {
  const { transcript, listening, resetTranscript } = useSpeechRecognition();
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSilenceTimer = () => {
    if (silenceTimer.current) {
      clearTimeout(silenceTimer.current);
      silenceTimer.current = null;
    }
  };

  const startListening = () => {
    SpeechRecognition.startListening({ continuous: true, language });
  };

  const stopListening = () => {
    SpeechRecognition.stopListening();
  };

  useEffect(() => {
    if (listening && transcript) {
      clearSilenceTimer();
      silenceTimer.current = setTimeout(() => {
        SpeechRecognition.stopListening();
      }, 3000); // 3초 침묵 시 자동 중지
    }

    return () => clearSilenceTimer();
  }, [transcript, listening]);

  return {
    transcript, // 음성인식 텍스트 결과
    listening, // 현재 마이크 활성화 상태 (boolean)
    startListening, // 음성인식 시작 함수
    stopListening, // 음성인식 중지 함수
    resetTranscript, // 음성인식 결과 초기화 함수
  };
};
