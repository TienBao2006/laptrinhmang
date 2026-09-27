from openai import OpenAI

client = OpenAI(
    api_key="sk-dd36a342e600c1d1-azc1uv-934c07c0",
    base_url="http://localhost:20218/v1"
)

MODEL = "gemini/gemini-3.8-flash-high"


while True:
    print("\n==============================")
    print("Nhập nội dung cho AI")
    print("Gõ 'exit' để thoát")
    print("==============================")

    user_input = input("\nBạn: ")

    if user_input.lower() == "exit":
        break

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        )

        answer = response.choices[0].message.content

        print("\n===== AI =====")
        print(answer)

        # GHI ĐÈ FILE CŨ
        with open("result.txt", "w", encoding="utf-8") as file:
            file.write(answer)

        print("\nĐã cập nhật result.txt")

    except Exception as e:
        print("\nLỗi:")
        print(e)