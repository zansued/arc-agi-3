import sys, json, os, urllib.request, urllib.error, http.cookiejar

# Setup cookie jar for session persistence
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def debug(msg):
    print(msg)


def main():
    # Step 1: Get CSRF token (with Origin header to pass origin check)
    csrf_token = ""
    try:
        req = urllib.request.Request(
            "http://localhost:80/api/csrf_token",
            method="GET",
            headers={"Origin": "http://localhost"}
        )
        resp = opener.open(req, timeout=10)
        body = resp.read().decode("utf-8")
        debug("CSRF response: " + body[:300])
        csrf_data = json.loads(body)
        if csrf_data.get("ok"):
            csrf_token = csrf_data.get("token", "")
            debug("CSRF token OK: " + str(csrf_token[:30]))
        else:
            debug("CSRF error: " + csrf_data.get("error", "unknown"))
    except Exception as e:
        debug("CSRF error: " + str(e))

    # Read prompt
    prompt = "Ola"
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.exists(arg) and os.path.isfile(arg):
            with open(arg, "r", encoding="utf-8") as f:
                prompt = f.read()
            debug("Prompt: " + str(len(prompt)) + " chars from " + arg)
        else:
            prompt = arg

    # Step 2: Send message via API
    try:
        headers = {
            "Content-Type": "application/json",
            "Origin": "http://localhost"
        }
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
        req = urllib.request.Request(
            "http://localhost:80/api/message_async",
            data=json.dumps({"text": prompt}).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        resp = opener.open(req, timeout=10)
        result = json.loads(resp.read().decode("utf-8"))
        debug("OK: " + json.dumps(result))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        debug("HTTP " + str(e.code) + ": " + body)
    except Exception as e:
        debug("ERRO: " + str(e))

    debug("auto_prompt finalizado")


if __name__ == "__main__":
    main()