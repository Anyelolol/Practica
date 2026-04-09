from collections import deque
from imutils.video import VideoStream
import numpy as np
import cv2
import argparse
import imutils
import time


def seleccionar_color(click, x, y, flags, param):
    global lower, upper

    if click == cv2.EVENT_LBUTTONDOWN:
        frame_hsv = param
        color = frame_hsv[y, x]
        h, s, v = int(color[0]), int(color[1]), int(color[2])

        tolerancia = 10
        lower = (max(0, h - tolerancia), max(0, s - 30), max(0, v - 30))
        upper = (min(179, h + tolerancia), min(255, s + 30), min(255, v + 30))


ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to (optional) video file")
ap.add_argument("-b", "--buffer", type=int, default=64, help="max buffer size")
args = vars(ap.parse_args())

lower = (0, 0, 0)
upper = (179, 255, 255)

pts = deque(maxlen=args["buffer"])

if not args.get("video", False):
    vs = VideoStream(src=0).start()
else:
    vs = cv2.VideoCapture(args["video"])
time.sleep(2.0)

cv2.namedWindow("Seguir punto")

while True:
    frame = vs.read()
    frame = frame[1] if args.get("video", False) else frame
    if frame is None:
        break
    frame = imutils.resize(frame, width=600)
    blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    cv2.setMouseCallback("Seguir punto", seleccionar_color, hsv)

    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL,
                            cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    center = None

    if len(cnts) > 0:
        c = max(cnts, key=cv2.contourArea)
        ((x, y), radius) = cv2.minEnclosingCircle(c)
        M = cv2.moments(c)
        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
        if radius > 10:
            cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 255), 2)
            cv2.circle(frame, center, 5, (0, 0, 255), -1)
    pts.appendleft(center)

    for i in range(1, len(pts)):
        if pts[i - 1] is None or pts[i] is None:
            continue
        thickness = int(np.sqrt(args["buffer"] / float(i + 1)) * 2.5)
        cv2.line(frame, pts[i - 1], pts[i],(0, 0, 255), thickness)
    cv2.imshow("Seguir punto", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
if not args.get("video", False):
    vs.stop()
else:
    vs.release()
