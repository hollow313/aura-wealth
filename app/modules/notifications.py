import requests

def send_discord_msg(webhook_url, title, content, color=11036919):
    if not webhook_url: return
    payload = {"embeds": [{"title": title, "description": content, "color": color}]}
    try: requests.post(webhook_url, json=payload, timeout=5)
    except: pass
