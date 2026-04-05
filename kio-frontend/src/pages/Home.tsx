import { SpeechInput } from "../components/SpeechInput";
import { TopBar } from "../components/TopBar";

export const Home = () => {
  return (
    <div>
      <TopBar />
      <h1>STT Test</h1>
      <SpeechInput />
    </div>
  );
};
