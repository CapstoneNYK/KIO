from dotenv import load_dotenv

# 평가 스크립트처럼 main 을 거치지 않고 ai 모듈을 바로 쓸 때도 .env 설정(OLLAMA_MODEL 등)을 읽는다
load_dotenv()
