import os
import cv2, mediapipe as mp, numpy as np, time, pytesseract
from textblob import TextBlob
import math
import sys
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import letter

# Optional OpenAI correction (LLM). Install 'openai' and set OPENAI_API_KEY to enable.
try:
    import openai
    OPENAI_AVAILABLE = True and (os.getenv("OPENAI_API_KEY") is not None)
    if OPENAI_AVAILABLE:
        openai.api_key = os.getenv("OPENAI_API_KEY")
except Exception:
    OPENAI_AVAILABLE = False

# Tesseract Path (update if needed)
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

class FingerAirWriter:
    def __init__(self):
        # Camera + canvas
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3,1280); self.cap.set(4,720)
        self.canvas = np.zeros((720,1280,3), np.uint8)
        self.ui_h = 100

        # Mediapipe hands
        self.mp_h = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.hands = self.mp_h.Hands(max_num_hands=1,
                                     min_detection_confidence=0.75,
                                     min_tracking_confidence=0.7)

        # UI colors
        self.bg = (20,20,20)
        self.text_c = (200,200,200)
        self.neon = (0,255,255)

        # Palettes, tools, shapes
        self.colors = [
            (255,255,255),(0,255,255),(0,255,0),(255,0,0),(255,255,0),(255,0,255),
            (128,0,128),(0,128,255),(128,128,0),(0,100,0),(50,150,200),(200,80,120)
        ]
        self.curr_color = self.colors[0]
        self.brush = 10
        self.eraser = 45
        self.brush_min = 2
        self.brush_max = 50

        self.buttons = ["Brush","Eraser","Clear","Convert","Undo","Redo"]
        self.shapes = ["Line","Rect","RectF","Circle","CircleF","Arrow",
                       "Triangle","Star","Heart","Ellipse","Pentagon"]
        self.export_buttons = ["SavePNG","SavePDF"]

        # State
        self.rects = []
        self.shape_mode = None
        self.start_point = None
        self.last = (0,0)
        self.smooth_q = []

        self.hover_btn = None
        self.hover_t = 0

        self.mode = "idle"
        self._candidate_mode = None
        self._candidate_time = 0
        self.mode_stable_delay = 0.18

        self.slider_y = 300
        self.slider_top = 150
        self.slider_bottom = 600
        self.slider_active = False

        self.menu_open = None
        self.menu_locked = False

        self.shape_cycle_mode = False
        self.shape_cycle_index = 0
        self.shape_cycle_last = 0
        self.shape_cycle_interval = 0.6
        self.shape_cycle_list = ["Triangle","Pentagon","Star"]

        self.anim_phase = 0.0

        # Undo / redo
        self.undo_stack = []
        self.redo_stack = []

        # Text display and live prediction
        self.last_text = ""         # text after Convert (saved)
        self.live_text = ""         # live/candidate prediction while writing
        self.last_draw_time = 0.0   # timestamp of most recent stroke
        self.live_delay = 0.8       # seconds to wait after last stroke before running live OCR
        self.live_last_run = 0.0    # last time live OCR ran

        # Mouse drawing
        self.mouse_down = False
        self.mouse_last = None

        # Window
        self.win = "AirWriter"
        cv2.namedWindow(self.win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.win,1280,720)
        cv2.setMouseCallback(self.win, self.mouse_event)

    def mouse_event(self, event, x, y, flags, param):
        if y < self.ui_h:
            if event in (cv2.EVENT_LBUTTONUP, cv2.EVENT_RBUTTONUP):
                self.mouse_down = False
                self.mouse_last = None
            return

        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse_down = True
            self.mouse_last = (x,y)
            self.save_state()
            self.last_draw_time = time.time()
        elif event == cv2.EVENT_MOUSEMOVE and self.mouse_down and self.mouse_last is not None:
            cv2.line(self.canvas, self.mouse_last, (x,y), self.curr_color, self.brush)
            self.mouse_last = (x,y)
            self.last_draw_time = time.time()
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_down = False
            self.mouse_last = None

    def save_state(self):
        self.undo_stack.append(self.canvas.copy())
        if len(self.undo_stack) > 40:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.canvas.copy())
            self.canvas = self.undo_stack.pop()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.canvas.copy())
            self.canvas = self.redo_stack.pop()

    def smooth(self, x, y):
        self.smooth_q.append((x,y))
        if len(self.smooth_q) > 6:
            self.smooth_q.pop(0)
        return int(np.mean([p[0] for p in self.smooth_q])), int(np.mean([p[1] for p in self.smooth_q]))

    def draw_ui(self, frame):
        self.rects = []
        cv2.rectangle(frame,(0,0),(1280,self.ui_h),(20,20,20),-1)

        tabs = ["Colors","Shapes","Tools","Export"]
        start_x = 300
        for t in tabs:
            rx1,ry1 = start_x,18
            rx2,ry2 = start_x+180,58
            cv2.rectangle(frame,(rx1,ry1),(rx2,ry2),(40,40,40),-1)
            cv2.putText(frame,t,(rx1+18,ry1+32),cv2.FONT_HERSHEY_SIMPLEX,0.75,self.text_c,2)
            if self.menu_open == t:
                b = 2 + int((math.sin(self.anim_phase*3)+1)*1.5)
                cv2.rectangle(frame,(rx1-2,ry1-2),(rx2+2,ry2+2),self.neon,b)
            self.rects.append((rx1,ry1,rx2,ry2,("tab",t)))
            start_x += 200

        cv2.putText(frame,f"Brush {self.brush}",(1100,140),cv2.FONT_HERSHEY_SIMPLEX,0.7,self.neon,2)
        cv2.line(frame,(1220,self.slider_top),(1220,self.slider_bottom),(120,120,120),2)
        cv2.circle(frame,(1220,self.slider_y),10,self.neon,-1)

        cv2.putText(frame,f"Mode: {self.mode}",(10,710),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,0),2)

        if self.live_text:
            cv2.putText(frame, f"Live: {self.live_text}", (10,680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

        cv2.putText(frame, "Text:", (900,680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        if self.last_text:
            display = self.last_text if len(self.last_text) <= 60 else self.last_text[:57] + "..."
            cv2.putText(frame, display, (960,680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

        if self.menu_open:
            self.draw_center_menu(frame,self.menu_open)

    def draw_center_menu(self, frame, menu_name):
        cx = 320; cy = 140; w = 600; h = 160
        anim_off = int((math.sin(self.anim_phase*2)+1)*4)
        cv2.rectangle(frame, (cx-20, cy-20+anim_off), (cx+w+20, cy+h+anim_off), (30,30,30), -1)
        cv2.putText(frame, menu_name, (cx+8, cy-6+anim_off), cv2.FONT_HERSHEY_SIMPLEX, 0.8, self.neon, 2)

        items = []
        if menu_name == "Colors": items = self.colors
        elif menu_name == "Shapes": items = self.shapes
        elif menu_name == "Tools": items = self.buttons
        elif menu_name == "Export": items = self.export_buttons

        ix = cx; iy = cy + 24 + anim_off
        for it in items:
            rx1, ry1 = ix, iy; rx2, ry2 = ix + 110, iy + 70
            if isinstance(it, tuple):
                cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), it, -1)
                if it == self.curr_color:
                    cv2.rectangle(frame, (rx1-3, ry1-3), (rx2+3, ry2+3), self.neon, 2)
            else:
                cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (45,45,45), -1)
                cv2.putText(frame, str(it), (rx1+8, ry1+44), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.text_c, 2)
                if menu_name == "Shapes" and self.shape_mode == it:
                    cv2.rectangle(frame, (rx1-3, ry1-3), (rx2+3, ry2+3), self.neon, 2)

            typ = "color" if isinstance(it, tuple) else ("shape" if menu_name=="Shapes" else ("export" if menu_name=="Export" else "btn"))
            self.rects.append((rx1, ry1, rx2, ry2, (typ, it)))
            ix += 120
            if ix + 120 > cx + w:
                ix = cx; iy += 90

    def hover(self, x, y):
        for rx1, ry1, rx2, ry2, (typ, val) in self.rects:
            if rx1 < x < rx2 and ry1 < y < ry2:
                if self.hover_btn != (typ, val):
                    self.hover_btn = (typ, val); self.hover_t = time.time()
                if time.time() - self.hover_t > 0.35:
                    if typ == "tab":
                        self.menu_open = val; self.menu_locked = True
                    else:
                        if typ == "color":
                            self.curr_color = val
                        elif typ == "btn":
                            if val == "Brush":
                                self.shape_mode = None
                            elif val == "Eraser":
                                self.shape_mode = None
                                self.curr_color = (0,0,0); self.brush = self.eraser
                            elif val == "Clear":
                                self.save_state(); self.canvas[:] = 0
                            elif val == "Convert":
                                self.convert_and_save()
                            elif val == "Undo":
                                self.undo()
                            elif val == "Redo":
                                self.redo()
                        elif typ == "shape":
                            self.shape_mode = val
                        elif typ == "export":
                            if val == "SavePNG":
                                name = f"export_{int(time.time())}.png"
                                cv2.imwrite(name, self.canvas)
                            elif val == "SavePDF":
                                pdfname = f"export_{int(time.time())}.pdf"
                                c = pdfcanvas.Canvas(pdfname, pagesize=letter)
                                tmp = "temp_export.png"
                                cv2.imwrite(tmp, self.canvas)
                                c.drawImage(tmp,0,0,width=612,height=720)
                                c.save()
                        if self.menu_locked:
                            self.menu_open = None; self.menu_locked = False
                return
        self.hover_btn = None
        if not self.menu_locked:
            self.menu_open = None

    def draw_shape(self, img, p1, p2):
        x1, y1 = p1; x2, y2 = p2
        cx, cy = (x1+x2)//2, (y1+y2)//2
        w, h = abs(x2-x1), abs(y2-y1)
        def pts(a): return np.array([(int(x),int(y)) for x,y in a])
        m = self.shape_mode
        if m == "Line":
            cv2.line(img, p1, p2, self.curr_color, 2)
        elif m == "Rect":
            cv2.rectangle(img, p1, p2, self.curr_color, 2)
        elif m == "RectF":
            cv2.rectangle(img, p1, p2, self.curr_color, -1)
        elif m == "Circle":
            r = int(math.hypot(x2-x1, y2-y1)); cv2.circle(img, p1, r, self.curr_color, 2)
        elif m == "CircleF":
            r = int(math.hypot(x2-x1, y2-y1)); cv2.circle(img, p1, r, self.curr_color, -1)
        elif m == "Ellipse":
            cv2.ellipse(img, (cx,cy), (w//2, h//2), 0, 0, 360, self.curr_color, 2)
        elif m == "Arrow":
            cv2.arrowedLine(img, p1, p2, self.curr_color, 3, tipLength=0.2)
        elif m == "Triangle":
            t = [(cx, min(y1,y2)), (min(x1,x2), max(y1,y2)), (max(x1,x2), max(y1,y2))]
            cv2.polylines(img, [pts(t)], True, self.curr_color, 2)
        elif m == "Pentagon":
            r = min(w,h)/2; a=[]
            for i in range(5):
                ang = -math.pi/2 + i*2*math.pi/5
                a.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))
            cv2.polylines(img, [pts(a)], True, self.curr_color, 2)
        elif m == "Star":
            R=min(w,h)/2; r=R*0.45; a=[]
            for i in range(10):
                ang=-math.pi/2 + i*math.pi/5
                rr = R if i%2==0 else r
                a.append((cx + rr*math.cos(ang), cy + rr*math.sin(ang)))
            cv2.polylines(img, [pts(a)], True, self.curr_color, 2)
        elif m == "Heart":
            a=[]; sx=w/2.5; sy=h/2.5
            for t in np.linspace(0,2*math.pi,200):
                x = 16*np.sin(t)**3
                y = 13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t)
                a.append((cx + sx*x/16, cy - sy*y/16))
            cv2.polylines(img, [pts(a)], True, self.curr_color, 2)

    def _preprocess_for_ocr(self, img, scale_up=False):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if scale_up:
            gray = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_LINEAR)
        gray = cv2.GaussianBlur(gray, (5,5), 0)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2,2), np.uint8)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        th = cv2.dilate(th, np.ones((2,2), np.uint8), iterations=1)
        return th

    def _tesseract_read(self, bin_img, psm=7):
        try:
            return pytesseract.image_to_string(bin_img, config=f"--psm {psm}").strip()
        except Exception as e:
            print("[OCR] Tesseract error:", e)
            return ""

    def _openai_correct(self, raw_text):
        if not OPENAI_AVAILABLE:
            return raw_text
        try:
            prompt = (
                "You are a helpful assistant that corrects noisy OCR output of handwriting. "
                "Return the corrected plain text only (no explanation). "
                "If the input is gibberish, return an empty string.\n\n"
                f"OCR: '''{raw_text}'''"
            )
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini" if "gpt-4o-mini" in openai.Model.list().__dict__ else "gpt-4o-mini",
                messages=[{"role":"user","content":prompt}],
                max_tokens=256,
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print("[OpenAI] correction failed:", e)
            return raw_text

    def run_live_ocr_if_needed(self):
        now = time.time()
        if self.last_draw_time == 0 or (now - self.last_draw_time < self.live_delay) or (now - self.live_last_run < 0.6):
            return

        preview_img = self.canvas.copy()
        if preview_img is None or preview_img.size == 0:
            self.live_text = ""
            self.live_last_run = now
            return

        bin_img = self._preprocess_for_ocr(preview_img, scale_up=True)
        raw = self._tesseract_read(bin_img, psm=7)
        if not raw:
            raw = self._tesseract_read(bin_img, psm=6)
        corrected = raw
        try:
            if raw:
                corrected = str(TextBlob(raw).correct())
        except Exception:
            corrected = raw

        if OPENAI_AVAILABLE and corrected:
            corrected2 = self._openai_correct(corrected)
            if corrected2:
                corrected = corrected2

        self.live_text = corrected if corrected else ""
        self.live_last_run = now

    def convert_and_save(self):
        tmp = self.canvas.copy()
        if tmp is None or tmp.size == 0:
            self.last_text = "(No input)"
            return

        gray_all = cv2.cvtColor(tmp, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_all, 10, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(mask)
        if coords is None:
            self.last_text = "(No handwriting found)"
            with open("notes.txt","a",encoding="utf-8") as f:
                f.write(self.last_text + "\n")
            return

        x, y, w, h = cv2.boundingRect(coords)
        pad = 8
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(1280 - x, w + 2*pad)
        h = min(720 - y, h + 2*pad)

        region = tmp[y:y+h, x:x+w].copy()
        bin_img = self._preprocess_for_ocr(region, scale_up=True)
        raw = self._tesseract_read(bin_img, psm=7)
        if not raw:
            raw = self._tesseract_read(bin_img, psm=6)

        corrected = raw
        try:
            if raw:
                corrected = str(TextBlob(raw).correct())
        except Exception:
            corrected = raw

        if OPENAI_AVAILABLE and corrected:
            corrected2 = self._openai_correct(corrected)
            if corrected2:
                corrected = corrected2

        self.last_text = corrected if corrected else "(No text detected)"

        self.save_state()
        cv2.rectangle(self.canvas, (x, y), (x + w, y + h), (0,0,0), -1)

        text = self.last_text.replace("\r","").strip()
        if not text:
            text = "(No text detected)"

        font = cv2.FONT_HERSHEY_SIMPLEX
        max_w = w - 12
        lines = []
        words = text.split()
        if not words:
            lines = [text]
        else:
            cur = words[0]
            for word in words[1:]:
                size_cur = cv2.getTextSize(cur, font, 1.0, 2)[0][0]
                size_try = cv2.getTextSize(cur + " " + word, font, 1.0, 2)[0][0]
                if size_try <= max_w:
                    cur = cur + " " + word
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)

        font_scale = 1.0
        thickness = 2
        txt_h = cv2.getTextSize("A", font, font_scale, thickness)[0][1]
        total_h = txt_h * len(lines) + 6*(len(lines)-1)
        while total_h > h - 6 and font_scale > 0.4:
            font_scale -= 0.1
            txt_h = cv2.getTextSize("A", font, font_scale, thickness)[0][1]
            total_h = txt_h * len(lines) + 6*(len(lines)-1)

        if total_h > h - 6:
            max_lines = max(1, (h - 6) // (txt_h + 6))
            if max_lines < len(lines):
                lines = lines[:max_lines]
                if lines and len(lines[-1]) > 3:
                    lines[-1] = lines[-1][:-3] + "..."

        start_y = y + 6 + txt_h
        for i, ln in enumerate(lines):
            tx = x + 6
            ty = start_y + i*(txt_h + 6)
            cv2.putText(self.canvas, ln, (tx, ty), font, font_scale, (255,255,255), thickness, cv2.LINE_AA)

        with open("notes.txt","a",encoding="utf-8") as f:
            f.write(self.last_text + "\n")

        self.live_text = ""

    def run(self):
        last_time = time.time()
        while True:
            now = time.time()
            dt = now - last_time
            last_time = now
            self.anim_phase += dt

            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            ui = np.full_like(frame, self.bg)
            self.draw_ui(ui)

            try:
                self.run_live_ocr_if_needed()
            except Exception as e:
                print("[LiveOCR] error:", e)

            res = self.hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            preview = self.canvas.copy()

            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0]
                ix, iy = self.smooth(int(lm.landmark[8].x*1280), int(lm.landmark[8].y*720))
                index_up, middle_up, ring_up, pinky_up, thumb_up = self.fingers_up_count(lm)

                if ix > 1180:
                    self.slider_active = True
                    self.slider_y = max(self.slider_top, min(self.slider_bottom, iy))
                    self.brush = int(np.interp(self.slider_y, [self.slider_top, self.slider_bottom],
                                               [self.brush_min, self.brush_max]))
                else:
                    self.slider_active = False

                if index_up and middle_up and ring_up and not pinky_up:
                    self.mode = "idle"
                else:
                    cand = "draw" if (index_up and not middle_up) else ("select" if (index_up and middle_up) else "idle")
                    if cand != self._candidate_mode:
                        self._candidate_mode = cand
                        self._candidate_time = now
                    if now - self._candidate_time >= self.mode_stable_delay:
                        self.mode = self._candidate_mode

                if self.mode == "draw" and not self.slider_active:
                    if iy > self.ui_h:
                        if self.shape_mode:
                            if self.start_point is None:
                                self.start_point = (ix, iy)
                                self.save_state()
                                self.last_draw_time = time.time()
                            else:
                                tmp = preview.copy()
                                self.draw_shape(tmp, self.start_point, (ix, iy))
                                preview = tmp
                        else:
                            if self.last == (0,0):
                                self.last = (ix, iy)
                                self.save_state()
                            cv2.line(self.canvas, self.last, (ix, iy), self.curr_color, self.brush)
                            self.last = (ix, iy)
                            self.last_draw_time = time.time()
                    else:
                        if self.shape_mode and self.start_point:
                            self.draw_shape(self.canvas, self.start_point, (ix, iy))
                            self.start_point = None
                        self.last = (0,0)

                elif self.mode == "select" and not self.slider_active:
                    if iy < 260:
                        self.hover(ix, iy)
                else:
                    if self.start_point and self.shape_mode:
                        self.draw_shape(self.canvas, self.start_point, (ix, iy))
                    self.start_point = None
                    self.last = (0,0)

                self.mp_draw.draw_landmarks(ui, lm, self.mp_h.HAND_CONNECTIONS)
                cv2.circle(ui, (ix, iy), 8, (0,255,255), -1)

            out = cv2.addWeighted(ui, 1.0, preview, 1.0, 0)
            cv2.imshow(self.win, out)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord('u'):
                self.undo()
            if key == ord('r'):
                self.redo()
            if key == ord('c'):
                self.convert_and_save()

        self.cap.release()
        cv2.destroyAllWindows()

    def fingers_up_count(self, lm):
        tips = [8,12,16,20]; pips = [6,10,14,18]
        ups = [lm.landmark[t].y < lm.landmark[p].y for t,p in zip(tips,pips)]
        thumb = lm.landmark[4].x < lm.landmark[3].x
        return ups[0], ups[1], ups[2], ups[3], thumb

if __name__ == "__main__":
    FingerAirWriter().run()
