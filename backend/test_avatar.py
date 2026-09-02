import asyncio

from app.avatar.service import AvatarService


async def main():

    avatar = AvatarService()

    video_path = await avatar.generate_video(
        audio_path="storage/audio/lesson_17_teacher.mp3",
        filename="test_teacher.mp4",
    )

    print("VIDEO GENERATED:")
    print(video_path)


if __name__ == "__main__":
    asyncio.run(main())