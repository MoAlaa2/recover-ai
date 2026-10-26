"""Terminal chat client for the ReCover consultant API.

Commands inside the chat: /image PATH uploads a room photo for the next
message, /quit exits.
"""
import argparse
import json
import sys
import urllib.request

DEFAULT_URL = "http://localhost:8000"


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_file(url, path):
    with open(path, "rb") as f:
        blob = f.read()
    boundary = "chatcli12345"
    name = path.split("/")[-1]
    body = (("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
             "filename=\"%s\"\r\n\r\n" % (boundary, name)).encode()
            + blob + ("\r\n--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def show_result(result):
    print("\n%s\n" % result.get("reply", ""))
    for rec in result.get("recommendations", []):
        print("  %(code)s | %(name_en)s | %(price_sar_per_m)d SAR/m\n"
              "    %(reason)s" % rec)
    room = result.get("room_analysis")
    if room:
        print("\n  Room: %s | style: %s | light: %s" % (
            room.get("room_type", "?"), room.get("style", "?"),
            room.get("light_level", "?")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--session", default="cli")
    args = parser.parse_args(argv)

    print("ReCover consultant. /image PATH to attach a photo, /quit to exit.")
    pending_image = None
    while True:
        try:
            line = input("you> ").strip()
        except EOFError:
            break
        if line == "/quit":
            break
        if line.startswith("/image "):
            path = line[len("/image "):].strip()
            try:
                pending_image = post_file(args.url + "/api/upload",
                                          path)["image_path"]
                print("attached: %s" % pending_image)
            except Exception as exc:  # noqa: BLE001 - show and continue
                print("upload failed: %s" % exc)
            continue
        if not line:
            continue
        payload = {"session_id": args.session, "message": line}
        if pending_image:
            payload["image_path"] = pending_image
            pending_image = None
        try:
            show_result(post_json(args.url + "/api/chat", payload))
        except Exception as exc:  # noqa: BLE001 - show and continue
            print("request failed: %s" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
