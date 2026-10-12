import json, os, sys, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor import extract_requirements, regex_extract, sd_prompt
from layout import generate_layout, validate, spec_from_requirements


class Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        body = json.dumps({"message": {"content": 'Sure! {"bhk": 2, "rooms": {"balcony": true, "kitchen": true}}'}}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass


class T(unittest.TestCase):
    def test_all_templates_valid(self):
        for bhk in (1, 2, 3):
            for bal in (True, False):
                lay = generate_layout({"bhk": bhk, "rooms": {"balcony": bal, "dining": bal}})
                self.assertEqual(validate(lay), [], (bhk, bal))

    def test_reference_1bhk_size(self):
        lay = generate_layout({"bhk": 1, "rooms": {"balcony": True}})
        self.assertEqual((lay.outer_w, lay.outer_h), (22.0, 28.0))

    def test_regex_and_limits(self):
        self.assertEqual(regex_extract("two bhk with balcony")["bhk"], 2)
        self.assertEqual(spec_from_requirements({"bhk": 5, "rooms": {}})["bhk"], 3)

    def test_llm_path_and_fallback(self):
        srv = HTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
        req, src = extract_requirements("2bhk", True, f"http://127.0.0.1:{srv.server_port}", "x")
        self.assertEqual(src, "llm"); self.assertEqual(req["bhk"], 2); self.assertTrue(req["rooms"]["balcony"])
        req, src = extract_requirements("1bhk", True, "http://127.0.0.1:9", "x", )
        self.assertTrue(src.startswith("regex (LLM failed"))

    def test_sd_prompt_format(self):
        p = sd_prompt(regex_extract("2BHK with balcony"))
        self.assertTrue(p.startswith("CAD architectural floor plan of a 2BHK house, with rooms: master bedroom"))


if __name__ == "__main__":
    unittest.main()
