// 서버 주소 한 곳 관리. 비워 두면(기본) 같은 주소의 /api 로 보내고, 개발 서버(vite)가 백엔드로 넘겨 준다.
// 다른 서버를 쓰려면 .env 에 VITE_API_URL=http://주소:포트 를 적는다.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "";
