import asyncio

from app.voice.tts import TTSService


async def main():
    tts = TTSService()

    output = await tts.generate_speech(
        text="வணக்கம். நான் EDUVA. இன்று நாம் விசையைப் பற்றி கற்றுக்கொள்ளப் போகிறோம்.",
        language="Tamil",
        filename="test_teacher_tamil.mp3",
    )

    print("TAMIL AUDIO GENERATED:")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())