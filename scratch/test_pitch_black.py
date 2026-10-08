import urllib.request

def test_pitch_black():
    req = urllib.request.urlopen("http://127.0.0.1:8000/")
    html = req.read().decode("utf-8")
    assert req.status == 200
    assert "hero-entry-screen" in html
    assert "#000000" in html
    print("[PASS] index.html serves pitch black elements")

    req_css = urllib.request.urlopen("http://127.0.0.1:8000/static/style.css")
    css = req_css.read().decode("utf-8")
    assert "--pitch-black: #000000;" in css
    assert "--nightshift: #000000;" in css
    assert "background-color: #000000;" in css
    print("[PASS] style.css serves pitch black design tokens")

    req_js = urllib.request.urlopen("http://127.0.0.1:8000/static/mesh-bg.js")
    js = req_js.read().decode("utf-8")
    assert "c_nightshift = vec3(0.0, 0.0, 0.0);" in js
    assert "canvas.style.backgroundColor = '#000000';" in js
    assert "document.body.style.backgroundColor = '#000000';" in js
    print("[PASS] mesh-bg.js serves pitch black WebGL shader & canvas background")

if __name__ == "__main__":
    test_pitch_black()
    print("ALL PITCH BLACK VERIFICATIONS SUCCEEDED!")
