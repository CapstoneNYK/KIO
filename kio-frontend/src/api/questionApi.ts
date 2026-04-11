export const questionApi = async (query: string): Promise<string> => {
  const response = await fetch("/api/question", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  const data = await response.json();
  return data.answer;
};
