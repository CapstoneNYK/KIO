import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";

export const useSTT = (language: string = "ko-KR") => {
  const { transcript, listening, resetTranscript } = useSpeechRecognition();

  const startListening = () => {
    SpeechRecognition.startListening({ continuous: true, language });
  };

  const stopListening = () => {
    SpeechRecognition.stopListening();
  };

  return {
    transcript, // 음성인식 텍스트 결과
    listening, // 현재 마이크 활성화 상태 (boolean)
    startListening, // 음성인식 시작 함수
    stopListening, // 음성인식 중지 함수
    resetTranscript, // 음성인식 결과 초기화 함수
  };
};
