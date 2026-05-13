
import base64
import json
import mimetypes
import sys

from app.db.session import SessionLocal
from app.env import load_env_file
from app.llm.qwen_client import QwenClient
from app.llm.qwen_mcp_agent import QwenMCPAgent


def _load_image_file(path: str) -> dict[str, str]:
    mime_type, _ = mimetypes.guess_type(path)
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return {
        "image_base64": encoded,
        "mime_type": mime_type or "image/png",
    }


def main() -> None:
    load_env_file()

    if len(sys.argv) < 2:
        print('Usage: python scripts/test_qwen_agent.py "查询语句" [--image-file 路径 | --image-url 地址]')
        raise SystemExit(1)

    query = sys.argv[1]
    images = []
    args = sys.argv[2:]

    while args:
        option = args.pop(0)
        if option == "--image-file" and args:
            images.append(_load_image_file(args.pop(0)))
            continue
        if option == "--image-url" and args:
            images.append({"image_url": args.pop(0)})
            continue
        print(f"Unknown argument: {option}")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        client = QwenClient()
        agent = QwenMCPAgent(db=db, llm_client=client)
        result = agent.run(query, images=images)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
