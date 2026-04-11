import { useSTT } from "../utils/sttUtil";
import { Button } from "./Button";
import { useState, useEffect } from "react";
import { questionApi } from "../api/questionApi";

export const SpeechInput = () => {
  const {
    transcript,
    listening,
    startListening,
    stopListening,
    resetTranscript,
  } = useSTT("ko-KR");

  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const handleButtonClick = () => {
    if (listening) {
      stopListening();
    } else {
      resetTranscript();
      setAnswer("");
      startListening();
    }
  };

  const handleAsk = async (query: string) => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      const answer = await questionApi(query);
      setAnswer(answer);
    } catch (error) {
      console.error(error);
      setAnswer("질문 처리 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  // 음성인식 중지되면 자동으로 API 호출
  useEffect(() => {
    if (!listening && transcript) {
      handleAsk(transcript);
    }
  }, [listening, transcript]);

  return (
    <div>
      <Button
        text={listening ? "음성 인식 중지" : "음성 인식 시작"}
        aria-pressed={listening}
        onClick={handleButtonClick}
      />
      <p>음성 인식 중 : {listening ? "예" : "아니요"}</p>
      <p>인식된 텍스트 : {transcript}</p>

      {loading && <p>답변 생성 중...</p>}
      {answer && <p>답변 : {answer}</p>}
    </div>
  );
};
