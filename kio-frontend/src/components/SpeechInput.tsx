import { useSTT } from "../utils/sttUtil";
import { Button } from "./Button";

export const SpeechInput = () => {
  const {
    transcript,
    listening,
    startListening,
    stopListening,
    resetTranscript,
  } = useSTT("ko-KR");

  const handleButtonClick = () => {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  };

  console.log(transcript);

  return (
    <div>
      <Button text="음성 인식 시작" onClick={handleButtonClick} />
      <p>음성 인식 중 : {listening ? "예" : "아니요"}</p>
      <p>인식된 텍스트 : {transcript}</p>

      <Button text="초기화" onClick={resetTranscript} />
    </div>
  );
};
